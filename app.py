from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
import os
import wave
import time

# NEW GEMINI SDK
from google import genai
from google.genai import types

import moviepy.video.fx as vfx

from vertexai.preview.vision_models import ImageGenerationModel
from google.cloud import texttospeech
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# NEW SDK CLIENT
client = genai.Client(api_key="AlzaSyD-RvgJSay11alWUO8hc1dWXmFg4poto0g")

app = Flask(__name__)
CORS(app)

if not os.path.exists('static'):
    os.makedirs('static')

# keep only last 10 videos
MAX_STORED_VIDEOS = 10


# ─────────────────────────────────────────────
# MODELS INIT
# ─────────────────────────────────────────────

# Imagen Model
image_model = ImageGenerationModel.from_pretrained(
    "imagen-3.0-fast-generate-001"
)

# Google TTS
tts_client = texttospeech.TextToSpeechClient()


# ─────────────────────────────────────────────
# SAVE WAV FILE
# ─────────────────────────────────────────────
def save_wave_file(filename, pcm_data, channels=1, sample_width=2, rate=24000):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


# ─────────────────────────────────────────────
# CLEANUP OLD VIDEOS
# ─────────────────────────────────────────────
def cleanup_old_videos():
    """Only keep last 10 video files"""

    files = [
        f for f in os.listdir("static")
        if f.startswith("video_") and f.endswith(".mp4")
    ]

    if len(files) > MAX_STORED_VIDEOS:

        files.sort(
            key=lambda x: os.path.getmtime(
                os.path.join("static", x)
            )
        )

        old = files[:-MAX_STORED_VIDEOS]

        for f in old:
            os.remove(os.path.join("static", f))


# ─────────────────────────────────────────────
# API ENDPOINT
# ─────────────────────────────────────────────
@app.route('/get-response', methods=['POST'])
def get_bot_response():

    user_message = request.json.get('message', '').lower()

    # ─────────────────────────────────────────
    # GEMINI PROMPT
    # ─────────────────────────────────────────
    prompt = f"""
You are a data processing bot. Your only function is to populate the template below based on the user's question.

CRITICAL RULES:
1. Generate a factual answer broken into short parts.
2. Each part MUST be separated by a single forward slash: /
3. Generate a corresponding image description for EACH answer part.
4. Each description MUST be separated by a single forward slash: /
5. The number of answer parts MUST EXACTLY MATCH the number of description parts.
6. ABSOLUTELY NO extra text.

OUTPUT TEMPLATE:

[ANSWER_START]
Answer Part 1 / Answer Part 2 / Answer Part 3
[ANSWER_END]

[DESCRIPTIONS_START]
Description 1 / Description 2 / Description 3
[DESCRIPTIONS_END]

User Question:
{user_message}
"""

    # ─────────────────────────────────────────
    # NEW GEMINI SDK CALL
    # ─────────────────────────────────────────
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    full_response_text = response.text

    # ─────────────────────────────────────────
    # PARSE RESPONSE
    # ─────────────────────────────────────────
    answer = full_response_text.split(
        '[ANSWER_START]'
    )[1].split('[ANSWER_END]')[0].strip()

    descriptions = full_response_text.split(
        '[DESCRIPTIONS_START]'
    )[1].split('[DESCRIPTIONS_END]')[0].strip()

    print("text done")

    # ─────────────────────────────────────────
    # IMAGE GENERATION
    # ─────────────────────────────────────────
    img_path = []

    for i, text in enumerate(descriptions.split('/')):

        response = image_model.generate_images(
            prompt=text.strip(),
            number_of_images=1,
            aspect_ratio="16:9"
        )

        filename = f"image_{i}.png"
        filepath = os.path.join('static', filename)

        response.images[0].save(location=filepath)

        img_path.append(filepath)

    print("image done")

    # ─────────────────────────────────────────
    # AUDIO GENERATION
    # ─────────────────────────────────────────
    audio_path = []

    for i, text_part in enumerate(answer.split('/')):

        if not text_part.strip():
            continue

        synthesis_input = texttospeech.SynthesisInput(
            text=text_part.strip()
        )

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

        with open(filepath, "wb") as out:
            out.write(response.audio_content)

        audio_path.append(filepath)

    print("audio done")

    # ─────────────────────────────────────────
    # VIDEO GENERATION
    # ─────────────────────────────────────────
    timestamp = int(time.time())

    video_filename = f"video_{timestamp}.mp4"

    output = os.path.join('static', video_filename)

    all_clips = []

    for image_file, audio_file in zip(img_path, audio_path):

        audio_clip = AudioFileClip(audio_file)

        image_clip = (
            ImageClip(image_file)
            .with_duration(audio_clip.duration)
            .with_audio(audio_clip)
        )

        # slight zoom effect
        final_clip = image_clip.resized(
            lambda t: 1 + 0.005 * t
        )

        all_clips.append(final_clip)

    final_video = concatenate_videoclips(
        all_clips,
        method="compose"
    )

    final_video.write_videofile(
        output,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate="96k",
        preset='ultrafast',
        fps=24
    )

    print("video done")

    # cleanup old videos
    cleanup_old_videos()

    # generate video URL
    video_url = url_for(
        'static',
        filename=video_filename,
        _external=True
    )

    return jsonify({
        "videoUrl": video_url,
        "answer": answer,
        "descriptions": descriptions,
        "images": img_path
    })


# ─────────────────────────────────────────────
# RUN APP
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
