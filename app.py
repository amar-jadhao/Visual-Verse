from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
import random
import os
import io
import base64
import wave
import time

import google.generativeai as genai
import moviepy.video.fx as vfx

from vertexai.preview.vision_models import ImageGenerationModel
from google.cloud import texttospeech
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
genai.configure(api_key="Add your api key mf")

app = Flask(__name__)
CORS(app)

if not os.path.exists('static'):
    os.makedirs('static')

# keep only last 10 videos
MAX_STORED_VIDEOS = 10


# ─────────────────────────────────────────────
#  MODELS INIT
# ─────────────────────────────────────────────
image_model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")
tts_client = texttospeech.TextToSpeechClient()
gemini_model = genai.GenerativeModel('gemini-2.5-flash')


# ─────────────────────────────────────────────
def save_wave_file(filename, pcm_data, channels=1, sample_width=2, rate=24000):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


def cleanup_old_videos():
    """Only keep last 10 video files"""
    files = [f for f in os.listdir("static") if f.startswith("video_") and f.endswith(".mp4")]
    if len(files) > MAX_STORED_VIDEOS:
        files.sort(key=lambda x: os.path.getmtime(os.path.join("static", x)))
        old = files[:-MAX_STORED_VIDEOS]
        for f in old:
            os.remove(os.path.join("static", f))


# ─────────────────────────────────────────────
#  API ENDPOINT
# ─────────────────────────────────────────────
@app.route('/get-response', methods=['POST'])
def get_bot_response():

    user_message = request.json.get('message', '').lower()

    # TEXT GEN
    prompt = f"""You are a data processing bot. Your only function is to populate the template below based on the user's question.

**CRITICAL RULES:**
1.  Generate a factual answer broken into short parts. Each part MUST be separated by a single forward slash: `/`.
2.  Generate a corresponding image description for EACH answer part. Each description MUST be separated by a single forward slash: `/`.
3.  The number of answer parts MUST EXACTLY MATCH the number of description parts.
4.  ABSOLUTELY NO other text, markdown, or explanations should be included in your response.

**OUTPUT TEMPLATE:**
[ANSWER_START]
Answer Part 1 / Answer Part 2 / Answer Part 3
[ANSWER_END]
[DESCRIPTIONS_START]
Description for Part 1 / Description for Part 2 / Description for Part 3
[DESCRIPTIONS_END]

---
**EXAMPLE:**
User's Question: What is a black hole?

Your Output:
[ANSWER_START]
A black hole is a region of spacetime where gravity is so strong that nothing, not even light, can escape. / They are formed from the remnants of massive stars that collapse under their own gravity. / The boundary of no return around a black hole is called the event horizon.
[ANSWER_END]
[DESCRIPTIONS_START]
A swirling, dark vortex in the fabric of space, bending the light of distant stars around its edge. / A colossal, brilliant blue star violently imploding, creating a magnificent supernova explosion. / A glowing, spherical boundary in the blackness of space, marking the final threshold before entering the black hole.
[DESCRIPTIONS_END]
---

Now, process the following user question and adhere strictly to all rules.

User's Question: {user_message}"""
    response = gemini_model.generate_content(prompt)
    full_response_text = response.text

    answer = full_response_text.split('[ANSWER_START]')[1].split('[ANSWER_END]')[0].strip()
    descriptions = full_response_text.split('[DESCRIPTIONS_START]')[1].split('[DESCRIPTIONS_END]')[0].strip()
    print("text done")

    # IMAGE GEN
    img_path = []
    for i, text in enumerate(descriptions.split('/')):
        response = image_model.generate_images(
            prompt=f"{text}",
            number_of_images=1,
            aspect_ratio="16:9"
        )

        filename = f"image_{i}.png"
        filepath = os.path.join('static', filename)

        response.images[0].save(location=filepath)
        img_path.append(filepath)

    print("image done")

    # AUDIO GEN
    audio_path = []
    for i, text_part in enumerate(answer.split('/')):
        if not text_part.strip():
            continue

        synthesis_input = texttospeech.SynthesisInput(text=text_part)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-F"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        filename = f"audio_{i}.wav"
        filepath = os.path.join('static', filename)
        save_wave_file(filepath, response.audio_content)
        audio_path.append(filepath)

    print("audio done")

    # VIDEO GEN ✅ (UPDATED)
    timestamp = int(time.time())
    video_filename = f"video_{timestamp}.mp4"
    output = os.path.join('static', video_filename)

    all_clips = []

    for image_file, audio_file in zip(img_path, audio_path):
        audio_clip = AudioFileClip(audio_file)
        image_clip = ImageClip(image_file)
        final_clip = image_clip.with_duration(audio_clip.duration).with_audio(audio_clip)

        final_clip = final_clip.resized(lambda t: 1 + 0.005 * t)
        all_clips.append(final_clip)

    final_video = concatenate_videoclips(all_clips, method="compose")

    final_video.write_videofile(
        output,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate="96k",
        preset='ultrafast',
        fps=1
    )

    cleanup_old_videos()  # ✅ remove older videos

    video_url = url_for('static', filename=video_filename, _external=True)

    return jsonify({
        "videoUrl": video_url,
        "answer": answer,
        "descriptions": descriptions,
        "images": img_path
    })


if __name__ == '__main__':
    app.run(debug=True)
