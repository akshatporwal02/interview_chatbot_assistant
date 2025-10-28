import os
import time
import pdfkit
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
from jinja2 import Environment, FileSystemLoader
import matplotlib.pyplot as plt
from datetime import datetime
import logging
from utils.env_utils import load_dotenv, get_openai_api_key
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

class ReportGenerator:
    def __init__(self, config):
        """
        Initialize the report generator with configuration

        Args:
            config (dict): Configuration dictionary from YAML
        """
        self.config = config.get('reporting', {})
        self.output_dir = self.config.get('output_dir', './reports/generated')
        self.image_dir = os.path.join(self.output_dir, 'images')
        
        # Ensure directories exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Configure templates
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.template_env = Environment(loader=FileSystemLoader(template_path))
        
        # Configure logging
        self.logger = logging.getLogger('ReportGenerator')
        self.logger.setLevel(logging.INFO)
        
        # Severity mapping
        self.severity_map = self.config.get('severity_levels', {})

        # LLM client (optional)
        self.llm_client = None
        try:
            load_dotenv()
            api_key = get_openai_api_key()
            if OpenAI and api_key:
                self.llm_client = OpenAI(api_key=api_key)
        except Exception:
            self.llm_client = None

    def generate_report(self, student_info, violations, candidate_analysis=None,
                       interviewer_analysis=None, decision=None,
                       transcript_text=None, meeting_info=None,
                       output_format='pdf'):
        """
        Generate a comprehensive interview/violation report
        """
        try:
            # Prepare report data
            report_data = {
                'student': student_info,
                'violations': violations,
                'grouped_violations': self._group_violations_by_type(violations),
                'transcript': transcript_text or "No transcript available.",
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'meeting_info': meeting_info or {},
                'stats': self._calculate_stats(violations),
                'timeline_image': self._generate_timeline(violations, student_info['id']),
                'heatmap_image': None,  # disabled for now
                'has_images': False,

                'job': {
                    'experience': student_info.get('experience', ''),
                    'position': student_info.get('position_applied_for', ''),
                    'jd_link': student_info.get('jd_link', ''),
                    'current_round': student_info.get('current_round', '')
                },
                'ai_remarks': student_info.get('ai_remarks', ''),
                'interviewer_name': student_info.get('interviewer_name', ''),
                'network_condition': student_info.get('network_condition', ''),
                'scheduled_by': student_info.get('scheduled_by', ''),
                'scheduled_by_email': student_info.get('scheduled_by_email', '')
            }

            report_data['candidate_analysis'] = candidate_analysis
            report_data['interviewer_analysis'] = interviewer_analysis
            report_data['decision'] = decision

            # Expose status for template convenience
            try:
                report_data['status'] = ((decision or {}).get('recommendation') or '').strip()
            except Exception:
                report_data['status'] = ''

            # Participant mapping: interviewer vs candidate based on rules
            # - Ignore participant named exactly 'strata(Bot)' (case-insensitive)
            # - Prefer any participant whose name/email contains 'concret.io' as Interviewer
            # - Remaining human becomes Candidate
            # - Display only names (no emails/IDs); if only email available, use local-part
            def _norm_name(x):
                try:
                    return str(x or '').strip()
                except Exception:
                    return ''

            def _get_identifier(p):
                """Return best identifier (email or name/string)."""
                if isinstance(p, dict):
                    return _norm_name(p.get('email') or p.get('name') or p.get('id'))
                return _norm_name(p)

            def _get_name_only(p):
                """Return a clean display name.
                Priority: dict.name > email local-part > raw string (no domain if email)
                """
                if isinstance(p, dict):
                    name = _norm_name(p.get('name'))
                    email = _norm_name(p.get('email'))
                    if name:
                        return name
                    if email and '@' in email:
                        return email.split('@', 1)[0]
                    rid = _norm_name(p.get('id'))
                    return rid
                s = _norm_name(p)
                if '@' in s:
                    return s.split('@', 1)[0]
                return s

            participants = []
            try:
                raw_parts = (meeting_info or {}).get('participants') or []
                # Filter out bot
                for p in raw_parts:
                    ident = _get_identifier(p)
                    if ident.lower() == 'strata(bot)':
                        continue
                    if ident:
                        participants.append(p)
            except Exception:
                participants = []

            interviewer_display = ''
            candidate_display = ''
            # Apply concret.io heuristic
            for part in participants:
                ident_str = _get_identifier(part).lower()
                if 'concret.io' in ident_str:
                    # Force interviewer display as 'concret.io' per requirement
                    interviewer_display = 'concret.io'
                else:
                    # prefer first non-concret.io as candidate
                    if not candidate_display:
                        candidate_display = _get_name_only(part)
            # Fallbacks
            if not candidate_display:
                # Prefer student's name; if only email, strip domain
                s_name = _norm_name(student_info.get('name'))
                s_email = _norm_name(student_info.get('email'))
                if s_name:
                    candidate_display = s_name
                elif s_email:
                    candidate_display = s_email.split('@', 1)[0] if '@' in s_email else s_email
                else:
                    candidate_display = ''
            if not interviewer_display:
                interviewer_display = _norm_name(student_info.get('interviewer_name'))

            # Final sanitization: never show IDs/emails for interviewer; prefer 'concret.io'
            def _looks_like_id_or_email(s: str) -> bool:
                s = _norm_name(s)
                if not s:
                    return True
                if '@' in s:
                    return True
                # UUID-like heuristic
                if len(s) >= 24 and '-' in s:
                    return True
                return False

            if _looks_like_id_or_email(interviewer_display):
                interviewer_display = 'concret.io'

            report_data['interviewer_display'] = interviewer_display
            report_data['candidate_display'] = candidate_display
            report_data['interviewer_display_name'] = interviewer_display
            report_data['candidate_display_name'] = candidate_display

            # Thresholds for violations
            violation_thresholds = {
                "TOTAL VIOLATIONS": {"critical": 7, "major": 5, "medium": 3},
                "FACE_DISAPPEARED": {"critical": 7, "major": 5, "medium": 3},
                "FORBIDDEN_OBJECT": {"critical": 3, "major": 2, "medium": 1},
                "MULTIPLE_FACES": {"critical": 3, "major": 2, "medium": 1},
                "EYE_MOVEMENT": {"critical": 5, "major": 4, "medium": 3}
            }
            report_data['thresholds'] = violation_thresholds

            # Legend explanations
            legend_explanations = {
                "TOTAL VIOLATIONS": "Total count of all detected violations.",
                "FACE_DISAPPEARED": "No face detected for a prolonged duration.",
                "FORBIDDEN_OBJECT": "Prohibited objects detected (e.g., phone, notes).",
                "MULTIPLE_FACES": "Multiple people detected in frame.",
                "EYE_MOVEMENT": "Suspicious or frequent gaze shifts."
            }
            report_data['legend_explanations'] = legend_explanations

            # Check if we have images to include
            if report_data['timeline_image'] or report_data['heatmap_image']:
                report_data['has_images'] = True

            # Map suspicious activity overall remark to final status as requested:
            # - Extremely Poor -> Rejected
            # - Poor -> On Hold
            try:
                susp_overall = report_data.get('stats', {}).get('overall_remark')
                if susp_overall:
                    susp_overall_norm = str(susp_overall).strip().lower()
                    # Ensure decision dict exists
                    if report_data.get('decision') is None:
                        report_data['decision'] = {}
                    # Keep the original status unless mapping applies and causes a change
                    forced_reason = None
                    original_rec = str((report_data['decision'] or {}).get('recommendation') or '').strip()
                    target_rec = None
                    if susp_overall_norm == 'extremely poor':
                        target_rec = 'Rejected'
                    elif susp_overall_norm == 'poor':
                        target_rec = 'On Hold'

                    if target_rec:
                        # Only mark as forced if we are changing the recommendation
                        if original_rec.lower() != target_rec.lower():
                            report_data['decision']['recommendation'] = target_rec
                            forced_reason = (
                                "The status has been marked as rejected due to an 'Extremely Poor' overall remark identified in the fraudulent statistics."
                                if target_rec == 'Rejected' else
                                "The status has been marked as on hold due to an 'Poor' overall remark identified in the fraudulent statistics."
                            )

                    # Expose the suspicious overall remark on decision for transparency
                    report_data['decision']['suspicious_overall_remark'] = report_data['stats'].get('overall_remark')
                    if forced_reason:
                        # Keep field for internal/debug use
                        report_data['decision']['forced_reason'] = forced_reason
                        # Append the reason into the summary line (single place to show it)
                        try:
                            existing_summary = (report_data['decision'].get('summary') or '').strip()
                            sep = ' ' if existing_summary and not existing_summary.endswith('.') else ' '
                            report_data['decision']['summary'] = (existing_summary + sep + forced_reason).strip()
                        except Exception:
                            pass
            except Exception:
                pass

            # Build Quick Summary section
            try:
                # Fraud Check: list unique violation categories present (once)
                by_type = report_data['stats'].get('by_type', {})
                fraud_bits = []
                if by_type.get('MULTIPLE_FACES', 0) > 0:
                    fraud_bits.append('Multiple faces detected')
                if by_type.get('FORBIDDEN_OBJECT', 0) > 0:
                    fraud_bits.append('Forbidden object detected')
                if by_type.get('FACE_DISAPPEARED', 0) > 0:
                    fraud_bits.append('Face disappeared events detected')
                if by_type.get('EYE_MOVEMENT', 0) > 0:
                    fraud_bits.append('Suspicious eye movement detected')
                fraud_text = ', '.join(fraud_bits) + '.' if fraud_bits else 'No fraud signals detected.'

                # Interview: summarize from candidate_analysis (robust to label/value variants)
                def _first_val(d: dict):
                    return (
                        d.get('value')
                        or d.get('evaluation')
                        or d.get('score')
                        or d.get('rating')
                        or d.get('summary')
                    )

                comm = tech = attitude = None
                if candidate_analysis:
                    for row in candidate_analysis:
                        key = str(row.get('criteria', row.get('aspect', ''))).strip().lower()
                        val = _first_val(row)
                        if not val:
                            continue
                        if 'communicat' in key:
                            comm = val
                        elif ('technical' in key) or ('docker' in key):
                            tech = val
                        elif 'attitude' in key:
                            attitude = val
                parts = []
                if comm:
                    parts.append(f"Communication {str(comm).lower()}")
                if tech:
                    parts.append(f"Technical skills {str(tech).lower()}")
                if attitude:
                    parts.append(f"Attitude {attitude}.")
                interview_text = '; '.join(parts)
                if interview_text and not interview_text.endswith('.'):
                    interview_text += '.'

                # System Suggests: concise one-liner generated by LLM
                dec = report_data.get('decision') or {}
                rec = (dec.get('recommendation') or '').strip()
                summ = (dec.get('summary') or '').strip()
                base_text = summ or rec
                sys_suggests = ''
                if base_text:
                    sys_suggests = self._summarize_one_line(base_text) or base_text

                report_data['quick_summary'] = {
                    'fraud_check': fraud_text,
                    'interview': interview_text or 'No interview summary.',
                    'system_suggests': sys_suggests or 'No suggestion.'
                }
            except Exception:
                report_data['quick_summary'] = None

            # Render HTML
            template = self.template_env.get_template('base_report.html')
            html_content = template.render(report_data)

            # Filename (mirror transcript pattern: room + session; exclude student ID)
            timestamp = (meeting_info or {}).get('session_timestamp') or datetime.now().strftime("%Y-%m-%d_%H%M%S")
            room_name = (meeting_info or {}).get('room_name') or (meeting_info or {}).get('room') or "unknown_room"
            
            filename = f"report_{room_name}_{timestamp}"

            output_path = os.path.join(self.output_dir, f"{filename}.{output_format.lower()}")

            # Output as PDF or HTML
            if output_format.lower() == 'pdf':
                options = {
                    'enable-local-file-access': None,
                    'margin-top': '10mm',
                    'margin-right': '10mm',
                    'margin-bottom': '10mm',
                    'margin-left': '10mm'
                }
                # Prefer configured wkhtmltopdf path if it exists; otherwise fall back to PATH
                pdfkit_path = self.config.get('wkhtmltopdf_path')
                pdf_config = None
                if pdfkit_path and os.path.exists(pdfkit_path):
                    pdf_config = pdfkit.configuration(wkhtmltopdf=pdfkit_path)
                # If no config provided or path doesn't exist, pdfkit will try to use wkhtmltopdf from PATH
                pdfkit.from_string(html_content, output_path, configuration=pdf_config, options=options)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

            self.logger.info(f"Report generated at: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to generate report: {str(e)}")
            # Provide hints depending on platform/config
            wk = self.config.get('wkhtmltopdf_path')
            if wk and not os.path.exists(wk):
                self.logger.error(f"Configured wkhtmltopdf path does not exist: {wk}. On Linux/Docker, install wkhtmltopdf in the image and leave this config empty.")
            else:
                self.logger.error("Ensure wkhtmltopdf is installed and available on PATH, or set reporting.wkhtmltopdf_path to a valid executable.")
            return None

    def _summarize_one_line(self, text: str) -> str:
        """Use LLM to produce a single concise sentence from the given text.
        Returns None on failure so caller can fallback.
        """
        try:
            if not self.llm_client:
                return None
            prompt = (
                "Summarize the following recommendation into one concise sentence (<= 25 words). "
                "Do not add extra details. Keep it neutral and actionable.\n\n" + str(text)
            )
            resp = self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=60,
            )
            content = (resp.choices[0].message.content or '').strip()
            # Ensure single line
            import re as _re
            content = _re.sub(r"\s+", " ", content)
            return content or None
        except Exception:
            return None

    def _calculate_stats(self, violations):
        """Calculate summary statistics from violations, including ratings."""
        # Define all possible suspicious activities
        all_activities = [
            'FACE_DISAPPEARED',
            'MULTIPLE_FACES', 
            'FORBIDDEN_OBJECT',
            'EYE_MOVEMENT'
            
           
        ]
        
        stats = {
            'total': len(violations),
            'by_type': {},
            'timeline': [],
            'severity_score': 0,
            'ratings': {},
            'all_activities': all_activities
        }

        # Initialize all activities with 0 count and Low criticality
        for activity in all_activities:
            stats['by_type'][activity] = 0
            stats['ratings'][activity] = 'Low'

        rating_rules = self.config.get("rating_thresholds", {})

        def rate(activity, count):
            if count == 0:
                return "Low"
            rules = rating_rules.get(activity, {"critical": 5, "major": 3, "medium": 2})
            if count >= rules["critical"]:
                return "Critical"
            elif count >= rules["major"]:
                return "Major"
            elif count >= rules["medium"]:
                return "Medium"
            else:
                return "Low"

        # Count actual violations
        for v in violations:
            v_type = v['type']
            if v_type == "FACE_REAPPEARED":
                continue
            if v_type in stats['by_type']:
                stats['by_type'][v_type] += 1
            stats['timeline'].append({
                'time': v['timestamp'],
                'type': v_type,
                'severity': self.severity_map.get(v_type, 1)
            })
            stats['severity_score'] += self.severity_map.get(v_type, 1)

        stats['average_severity'] = (
            stats['severity_score'] / stats['total'] if stats['total'] else 0
        )

        # Update ratings for all activities
        for activity in all_activities:
            count = stats['by_type'][activity]
            stats['ratings'][activity] = rate(activity, count)

        # Overall remark based on presence of any severity level
        if stats['total'] == 0:
            stats['overall_remark'] = "Excellent"
        else:
            ratings_present = set(stats['ratings'].values())
            if "Critical" in ratings_present:
                stats['overall_remark'] = "Extremely Poor"
            elif "Major" in ratings_present:
                stats['overall_remark'] = "Poor"
            elif "Medium" in ratings_present:
                stats['overall_remark'] = "Good"
            else:
                stats['overall_remark'] = "Average"

        return stats

    def _group_violations_by_type(self, violations):
        """Group violations by type for organized display"""
        grouped = {}
        violation_categories = {
            'FACE_DISAPPEARED': 'Face Detection Violations',
            'MULTIPLE_FACES': 'Multiple Faces Detected',
            'FORBIDDEN_OBJECT': 'Forbidden Objects Detected',
            'EYE_MOVEMENT': 'Eye Tracking Violations',
            'EYE_TRACKING_ERROR': 'Detection System Errors'
            
        }
        for v in violations:
            v_type = v['type']
            category = violation_categories.get(v_type, v_type.replace('_', ' ').title())
            if category not in grouped:
                grouped[category] = {'category_name': category, 'violations': []}
            grouped[category]['violations'].append(v)

        for group in grouped.values():
            group['violations'].sort(key=lambda x: x['timestamp'])
        return grouped

    def _generate_timeline(self, violations, student_id):
        """Generate violation timeline visualization"""
        if not violations:
            return None
        try:
            times, severities, labels = [], [], []
            for v in violations:
                v_type = v['type']
                if v_type == "FACE_REAPPEARED":
                   continue
                t = datetime.strptime(v['timestamp'], "%Y-%m-%d_%H:%M:%S")
                times.append(t)
                severities.append(self.severity_map.get(v['type'], 1))
                labels.append(v['type'])

            plt.figure(figsize=(12, 5))
            plt.plot(times, severities, 'o-', markersize=8)
            for time, sev, label in zip(times, severities, labels):
                plt.annotate(label, (time, sev), textcoords="offset points",
                             xytext=(0, 10), ha='center', fontsize=8)

            plt.title(f"Violation Timeline")
            plt.xlabel("Time")
            plt.ylabel("Severity Level")
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45)
            plt.tight_layout()

            path = os.path.abspath(os.path.join(self.image_dir, f'timeline_{student_id}.png'))
            plt.savefig(path, dpi=150, bbox_inches='tight')
            plt.close()
            return path
        except Exception as e:
            self.logger.error(f"Failed to generate timeline: {str(e)}")
            return None

