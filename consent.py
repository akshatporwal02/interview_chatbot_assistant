import time

def send_consent_message(page):
    """
    Sends the entire consent message as a single chat message using Playwright fill().
    """
    consent_message = (
        "📋 **Consent Form Summary**\n\n"
        "🔹 **Consent to Access Camera and Microphone**\n"
        "By continuing, you consent to grant access to your device’s camera and microphone for the duration of the interview. "
        "This is strictly for communication and evaluation purposes.\n\n"
        "🔹 **Recording and Monitoring Notice**\n"
        "The entire interview will be recorded (audio, video, and screen). "
        "Your session will be monitored for any suspicious behavior. "
        "We will analyze your behavior, facial expressions, communication style, and surroundings.\n\n"
        "🔹 **Background Effects Restriction**\n"
        "Do not use virtual backgrounds or visual effects. Keep your real background visible and clear.\n\n"
        "🔹 **Interview Guidelines**\n"
        "✅ Sit in a well-lit, quiet environment / enable the extra noise suppression feature in Jitsi.\n"
        "✅ Keep your face clearly visible\n"
        "✅ Use headphones or a good mic\n"
        "✅ Do not leave the screen or disable your camera/mic\n"
        "✅ Avoid unauthorized help or tools\n"
        "✅ Keep your phone on silent or away\n"
        "✅ Ensure a stable internet connection\n\n"
        "💬 Please type **I Agree** in the chat to confirm your consent."
    )

    # Open chat
    page.keyboard.press("c")
    time.sleep(1)

    # Fill chat textarea using Playwright's native fill()
    try:
        page.fill('textarea', consent_message)
        time.sleep(0.5)
        page.keyboard.press("Enter")
        print("✅ Consent message sent as single chat bubble.")
    except Exception as e:
        print(f"❌ Failed to send consent message: {e}")


def wait_for_consent(page, timeout_seconds=300):
    """Wait for participant to type 'I Agree' in chat."""
    print("🔍 Waiting for participant consent in chat...")

    def extract_messages():
        return page.evaluate("""
            () => {
                const nodes = Array.from(document.querySelectorAll('.usermessage p'));
                return nodes.map(p => {
                    const clone = p.cloneNode(true);
                    const sr = clone.querySelector('.sr-only');
                    if (sr) sr.remove();
                    return clone.textContent.trim().toLowerCase();
                });
            }
        """)

    initial_messages = extract_messages()
    consent_received = False
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        current_messages = extract_messages()
        new_messages = [msg for msg in current_messages if msg not in initial_messages]

        for msg in new_messages:
            cleaned = msg.replace('"', '').strip()
            if cleaned in ["i agree", "yes i agree", "agree"]:
                consent_received = True
                print("✅ Consent received.")
                page.keyboard.press("c")
                time.sleep(0.5)
                page.keyboard.type("✅ Consent received. Thank you! You may now begin the interview.")
                page.keyboard.press("Enter")
                return True
            elif cleaned in ["not agree", "disagree", "i do not agree", "i don't agree", "no i don't agree"]:
                print("⚠️ Participant disagreed with consent.")
                page.keyboard.press("c")
                time.sleep(0.5)
                page.keyboard.type("⚠️ Consent is mandatory to proceed. Please type 'I Agree' to continue.")
                page.keyboard.press("Enter")
                initial_messages.append(msg)

        time.sleep(3)

    print("❌ No consent received within the time limit.")
    return False
