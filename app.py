import streamlit as st
import whisper
import subprocess
import os
import uuid
import time
import shutil

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# FFmpeg configuration
def get_ffmpeg_path():
    # First check if FFmpeg is in PATH
    if shutil.which('ffmpeg'):
        return 'ffmpeg'
    
    # For local development with custom FFmpeg path
    local_ffmpeg = r"C:\Users\sanya\Downloads\ffmpeg-2025-05-21-git-4099d53759-full_build\ffmpeg-2025-05-21-git-4099d53759-full_build\bin\ffmpeg.exe"
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    
    # If FFmpeg is not found, raise an error
    raise Exception("FFmpeg not found. Please install FFmpeg or check your PATH.")

# Try to get FFmpeg path, but don't fail if not found (will be handled during video processing)
try:
    FFMPEG_PATH = get_ffmpeg_path()
    if FFMPEG_PATH != 'ffmpeg':  # Only add to PATH if it's a local path
        os.environ["PATH"] += os.pathsep + os.path.dirname(FFMPEG_PATH)
except Exception as e:
    st.warning("FFmpeg not found. Some features may not work properly.")

st.title("MyntMore Video Transcriber 🎬📝")

# Add video source selection
video_source = st.radio("Select Video Source:", ["Instagram Reel", "YouTube Video"])

# Add model size selection with 'small' as default
model_size = st.selectbox(
    "Select Model Size (larger = more accurate but slower):",
    ["base", "small", "medium", "large"],
    index=1  # Set 'small' as default (index 1)
)

if video_source == "Instagram Reel":
    video_url = st.text_input("Paste Instagram Reel URL:")
else:
    video_url = st.text_input("Paste YouTube Video URL:")

if video_url and st.button("Transcribe Video"):
    with st.spinner("Downloading video..."):
        unique_id = str(uuid.uuid4())
        output_file = f"video_{unique_id}.mp4"
        try:
            subprocess.run(
                ["yt-dlp", "-o", output_file, video_url],
                check=True
            )
        except subprocess.CalledProcessError:
            st.error("Failed to download the video. Check the URL or try again.")
            st.stop()

    with st.spinner("Loading Whisper model..."):
        try:
            model = whisper.load_model(model_size)
        except Exception as e:
            st.error(f"Failed to load Whisper model: {str(e)}")
            if os.path.exists(output_file):
                os.remove(output_file)
            st.stop()

    with st.spinner("Transcribing with Whisper..."):
        try:
            # Transcribe with automatic language detection
            result = model.transcribe(
                output_file,
                fp16=False,  # Use CPU for better compatibility
                verbose=True,
                condition_on_previous_text=True,  # Better context awareness
                initial_prompt="This video contains both English and Hindi words. Please transcribe all words accurately."
            )
            
            # Display the full transcript
            st.subheader("Transcript:")
            full_text = result["text"]
            st.text_area("", full_text, height=300)
            
            # Display detected language
            if "language" in result:
                st.info(f"Detected Language: {result['language']}")
            
        except Exception as e:
            st.error(f"Transcription failed: {str(e)}")
        finally:
            # Cleanup downloaded video file
            if os.path.exists(output_file):
                os.remove(output_file)
