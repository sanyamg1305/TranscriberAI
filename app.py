import streamlit as st
import whisper
import subprocess
import os
import uuid

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

def download_video(url, output_file, is_instagram=False):
    """Download video with specific options based on source"""
    try:
        if is_instagram:
            # Instagram specific options
            command = [
                "yt-dlp",
                "--no-playlist",
                "--no-warnings",
                "--extractor-args", "instagram:logged_in=false",
                "-f", "best[ext=mp4]/best",
                "-o", output_file,
                url
            ]
        else:
            # YouTube specific options
            command = [
                "yt-dlp",
                "--no-playlist",
                "--no-warnings",
                "-f", "best[ext=mp4]/best",
                "-o", output_file,
                url
            ]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"Download failed: {e.stderr}")
        return False
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return False

if video_url and st.button("Transcribe Video"):
    with st.spinner("Downloading video..."):
        unique_id = str(uuid.uuid4())
        output_file = f"video_{unique_id}.mp4"
        
        # Download the video
        is_instagram = video_source == "Instagram Reel"
        if not download_video(video_url, output_file, is_instagram):
            st.error("Failed to download the video. Please check the URL and try again.")
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
