import io
import os
import random
import subprocess
from datetime import datetime

import speech_recognition as sr
from flask import Flask, jsonify, render_template, request
from pydub import AudioSegment
from pydub.utils import which
from textblob import TextBlob  # Add this import


# ======================
# FFmpeg Configuration
# ======================
def configure_ffmpeg():
    """Configure FFmpeg with explicit path from your downloads"""
    custom_ffmpeg_path = r"C:\path\to\ffmpeg.exe"  # Update path to your FFmpeg
    custom_ffprobe_path = r"C:\path\to\ffprobe.exe"  # Update path to your FFmpeg

    if os.path.exists(custom_ffmpeg_path) and os.path.exists(custom_ffprobe_path):
        try:
            subprocess.run([custom_ffmpeg_path, "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            AudioSegment.converter = custom_ffmpeg_path
            AudioSegment.ffprobe = custom_ffprobe_path
            print(f"Using FFmpeg at: {custom_ffmpeg_path}")
            return True
        except Exception as e:
            print(f"FFmpeg verification failed: {str(e)}")

    try:
        ffmpeg_path = which("ffmpeg")
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            subprocess.run([ffmpeg_path, "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffprobe = which("ffprobe")
            print(f"Using auto-detected FFmpeg at: {ffmpeg_path}")
            return True
    except Exception:
        pass

    print("Warning: FFmpeg not properly configured!")
    return False


if not configure_ffmpeg():
    print("\n⚠️ FFmpeg not properly configured!\n")

# ======================
# Flask Application
# ======================
app = Flask(__name__)

# Configuration
app.config.update(
    UPLOAD_FOLDER=os.path.join(app.static_folder, 'audio'),
    SECRET_KEY='your-secret-key-here',
    ALLOWED_EXTENSIONS={'webm', 'wav'},
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB
)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ======================
# Utility Functions
# ======================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def convert_audio(audio_bytes, input_format='webm'):
    """Convert audio bytes to WAV format with robust error handling"""
    try:
        if AudioSegment.converter:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=input_format)
            audio = audio.set_frame_rate(16000).set_channels(1)
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()
    except Exception as e:
        raise ValueError(f"Audio conversion failed: {str(e)}")


# ======================
# Application Routes
# ======================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/sentiment')
def sentiment_analysis():
    return render_template('sentiment.html')

@app.route('/voice')
def voice_assistant():
    return render_template('voice.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/analyze_sentiment', methods=['POST'])
def analyze_sentiment():
    text = request.form.get('text', '')
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    sentiment = 'positive' if polarity > 0 else 'negative' if polarity < 0 else 'neutral'
    
    return jsonify({
        'sentiment': sentiment,
        'polarity': float(polarity),
        'subjectivity': float(analysis.sentiment.subjectivity)
    })


@app.route('/process_voice', methods=['POST'])
def process_voice():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio_data']
    
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(audio_file.filename):
        return jsonify({'error': 'Only WEBM or WAV files are allowed'}), 400
    
    temp_path = None
    try:
        # Save to temporary file
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}.webm")
        audio_file.save(temp_path)
        
        # Convert to WAV format
        if AudioSegment.converter:
            audio = AudioSegment.from_file(temp_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_data = wav_buffer.getvalue()

        # Recognize speech
        r = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_data)) as source:
            audio = r.record(source)
            text = r.recognize_google(audio)
            response = process_voice_command(text.lower())
            
            return jsonify({
                'success': True,
                'text': text,
                'response': response
            })
            
    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand audio. Please speak clearly.'}), 400
    except sr.RequestError as e:
        return jsonify({'error': f'Speech recognition service error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error processing audio: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def process_voice_command(command):
    """Process voice commands with comprehensive responses"""
    responses = {
        'hello': ["Hello there!", "Hi!", "Greetings!"],
        'hi': ["Hello!", "Hi there!"],
        'time': [f"The current time is {datetime.now().strftime('%H:%M:%S')}"],
        'date': [f"Today's date is {datetime.now().strftime('%Y-%m-%d')}"],
        'how are you': ["I'm doing great, thanks for asking! How about you?", "I'm doing well! How can I assist you today?"],
        'what is your name': ["I'm your friendly assistant!", "I go by the name Bot. How can I help you today?"],
        'thank you': ["You're welcome!", "Glad to help!", "Anytime!"],
        'plan for the day': ["Here's your plan for the day:\n1. Start the day with a healthy breakfast.\n2. Attend the team meeting at 10 AM.\n3. Work on the project report.\n4. Take a break and go for a walk at noon.\n5. Continue with tasks and finish up by 6 PM.\n6. Relax in the evening and get some rest!"],
        'goodbye': ["Goodbye! Have a great day!", "See you later!", "Take care!"],
        'good morning': ["Good morning! Hope you have a wonderful day ahead!", "Good morning! How can I assist you today?"],
        'good night': ["Good night! Sleep well!", "Sweet dreams! Good night!"],
        'what can you do': ["I can help with sentiment analysis, provide voice assistance, and assist with various other tasks. How can I help you today?"],
        'default': ["I didn't understand that, could you rephrase it?"]
    }
    
    command = command.lower()
    for key in responses:
        if key in command:
            return random.choice(responses[key])
    return random.choice(responses['default'])

@app.route('/chatbot_response', methods=['POST'])
def chatbot_response():
    user_message = request.form.get('message', '').lower()
    
    responses = {
        'hello': ["Hi there!", "Hello!"],
        'hi': ["Hello!", "Hi there!"],
        'admission': ["The TNEA admission process starts after results. Keep checking the official website."],
        'counseling schedule': ["The counseling schedule is available on the official TNEA website."],
        'document': ["The required documents are 10th, 12th marksheets, community certificate, etc."],
        'cutoff scores': ["The cutoff scores for TNEA will be released after the results. Please check the official TNEA website for updates."],
        'registration process': ["To register for TNEA, visit the official website and follow the instructions provided. Make sure to fill in all necessary details and upload required documents."],
        'seat allocation': ["Seat allocation for TNEA will be based on your rank and preferences. Check the official website for more details on the allocation process."],
        'fees': ["The TNEA fees vary depending on the category and the course. Please refer to the official website for detailed fee information."],
        'eligibility': ["To be eligible for TNEA, you must have completed your 12th standard or equivalent examination with the required subjects and marks. For detailed eligibility criteria, please visit the official website."],
        'entrance exam': ["The TNEA process doesn't require an entrance exam, as it is based on your 12th standard marks. Please refer to the official website for more details."],
        'results': ["The TNEA results will be announced after the examination process. Please keep checking the official website for updates."],
        'default': ["I'm not sure I understand, can you elaborate?"]
    }
    
    for key in responses:
        if key in user_message:
            return jsonify({'response': random.choice(responses[key])})
    return jsonify({'response': random.choice(responses['default'])})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
