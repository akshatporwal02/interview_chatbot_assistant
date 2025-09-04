import os
import time
import pdfkit
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
from jinja2 import Environment, FileSystemLoader
import matplotlib.pyplot as plt
from datetime import datetime
import logging

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
        self.severity_map = {
            'FACE_DISAPPEARED': 1,
            'GAZE_AWAY': 2,
            'MULTIPLE_FACES': 4,
            'OBJECT_DETECTED': 5,
            'AUDIO_DETECTED': 3
        }

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

            # Render HTML
            template = self.template_env.get_template('base_report.html')
            html_content = template.render(report_data)

            # Filename (mirror transcript pattern: room + session; include student ID when present)
            timestamp = (meeting_info or {}).get('session_timestamp') or datetime.now().strftime("%Y-%m-%d_%H%M%S")
            room_name = (meeting_info or {}).get('room_name') or (meeting_info or {}).get('room') or "unknown_room"
            student_id = (str(student_info.get('id') or "")).strip()

            if student_id:
                filename = f"report_{room_name}_{student_id}_{timestamp}"
            else:
                filename = f"report_{room_name}_{timestamp}"

            output_path = os.path.join(self.output_dir, f"{filename}.{output_format.lower()}")

            # Output as PDF or HTML
            if output_format.lower() == 'pdf':
                options = {
                    'enable-local-file-access': None,
                    'quiet': '',
                    'margin-top': '10mm',
                    'margin-right': '10mm',
                    'margin-bottom': '10mm',
                    'margin-left': '10mm'
                }
                pdfkit_path = self.config.get('wkhtmltopdf_path')
                pdf_config = pdfkit.configuration(wkhtmltopdf=pdfkit_path) if pdfkit_path else None
                pdfkit.from_string(html_content, output_path, configuration=pdf_config, options=options)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

            self.logger.info(f"Report generated at: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to generate report: {str(e)}")
            return None

    def _calculate_stats(self, violations):
        """Calculate summary statistics from violations, including ratings."""
        stats = {
            'total': len(violations),
            'by_type': {},
            'timeline': [],
            'severity_score': 0,
            'ratings': {}
        }

        rating_rules = self.config.get("rating_thresholds", {})

        def rate(activity, count):
            rules = rating_rules.get(activity, {"critical": 5, "major": 3, "medium": 2})
            if count >= rules["critical"]:
                return "Critical"
            elif count >= rules["major"]:
                return "Major"
            elif count >= rules["medium"]:
                return "Medium"
            else:
                return "Low"

        for v in violations:
            v_type = v['type']
            if v_type == "FACE_REAPPEARED":
                continue
            stats['by_type'][v_type] = stats['by_type'].get(v_type, 0) + 1
            stats['timeline'].append({
                'time': v['timestamp'],
                'type': v_type,
                'severity': self.severity_map.get(v_type, 1)
            })
            stats['severity_score'] += self.severity_map.get(v_type, 1)

        stats['average_severity'] = (
            stats['severity_score'] / stats['total'] if stats['total'] else 0
        )

        for v_type, count in stats['by_type'].items():
            stats['ratings'][v_type] = rate(v_type, count)

        # Overall remark
        if stats['total'] <= 1:
            stats['overall_remark'] = "Excellent"
        elif stats['total'] <= 3:
            stats['overall_remark'] = "Good"
        elif stats['total'] <= 5:
            stats['overall_remark'] = "Average"
        else:
            stats['overall_remark'] = "Poor"

        return stats

    def _group_violations_by_type(self, violations):
        """Group violations by type for organized display"""
        grouped = {}
        violation_categories = {
            'FACE_DISAPPEARED': 'Face Detection Violations',
            'MULTIPLE_FACES': 'Multiple Faces Detected',
            'FORBIDDEN_OBJECT': 'Forbidden Objects Detected',
            'OBJECT_DETECTION_ERROR': 'Detection System Errors',
            'EYE_MOVEMENT': 'Eye Tracking Violations',
            'EYE_TRACKING_ERROR': 'Detection System Errors',
            'AUDIO_DETECTED': 'Audio Violations',
            'MOVEMENT_DETECTED': 'Movement Violations',
            'SUSPICIOUS_ACTIVITY': 'Suspicious Activity',
            'PHONE_DETECTED': 'Phone Detection',
            'PERSON_DETECTED': 'Person Detection'
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
                t = datetime.strptime(v['timestamp'], "%Y-%m-%d_%H:%M:%S")
                times.append(t)
                severities.append(self.severity_map.get(v['type'], 1))
                labels.append(v['type'])

            plt.figure(figsize=(12, 5))
            plt.plot(times, severities, 'o-', markersize=8)
            for time, sev, label in zip(times, severities, labels):
                plt.annotate(label, (time, sev), textcoords="offset points",
                             xytext=(0, 10), ha='center', fontsize=8)

            plt.title(f"Violation Timeline - {student_id}")
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
