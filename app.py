import streamlit as st
import whisper
import subprocess
import os
import uuid
import time
import json

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

def download_video(url, output_file, is_instagram=False, max_retries=3):
    """Download video with specific options based on source"""
    for attempt in range(max_retries):
        try:
            if is_instagram:
                # Instagram specific options with additional parameters
                command = [
                    "yt-dlp",
                    "--no-playlist",
                    "--no-warnings",
                    "--extractor-args", "instagram:logged_in=false",
                    "--cookies-from-browser", "chrome",
                    "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "--retries", "10",
                    "--fragment-retries", "10",
                    "--file-access-retries", "10",
                    "--extractor-retries", "10",
                    "--verbose",  # Add verbose output
                    "--dump-json",  # Get video info
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
                    "--verbose",  # Add verbose output
                    "--dump-json",  # Get video info
                    "-f", "best[ext=mp4]/best",
                    "-o", output_file,
                    url
                ]
            
            # First try to get video info
            info_command = command.copy()
            info_command.insert(-2, "--skip-download")
            info_result = subprocess.run(
                info_command,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse video info
            try:
                video_info = json.loads(info_result.stdout)
                st.info(f"Video title: {video_info.get('title', 'Unknown')}")
                st.info(f"Duration: {video_info.get('duration', 'Unknown')} seconds")
            except:
                st.warning("Could not parse video information")
            
            # Now try to download
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return True
            else:
                st.error("Download completed but file is empty or missing")
                return False
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr
            st.error(f"Detailed error: {error_msg}")
            
            if "429" in error_msg and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                st.warning(f"Rate limited. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                continue
            elif "Video unavailable" in error_msg:
                st.error("This video is unavailable. It might be private or deleted.")
            elif "Sign in" in error_msg:
                st.error("This video requires authentication. Please use a public video.")
            elif "Unable to download webpage" in error_msg:
                st.error("Could not access the video. Please check if the URL is correct and the video is public.")
            return False
            
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            return False
    
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
