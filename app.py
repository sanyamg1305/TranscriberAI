import streamlit as st
import whisper
import subprocess
import os
import uuid
import time
import json
import re
import platform
import shutil
import requests
import zipfile

st.title("MyntMore Video Transcriber 🎬📝")

# Add video source selection
video_source = st.radio("Select Video Source:", ["Instagram Reel", "YouTube Video"])

# Add model size selection with 'small' as default
model_size = st.selectbox(
    "Select Model Size (larger = more accurate but slower):",
    ["base", "small", "medium", "large"],
    index=1  # Set 'small' as default (index 1)
)

# Add an expander for advanced options like cookies
cookies = ""
if video_source == "Instagram Reel":
    with st.expander("Advanced Options (for Instagram issues)"):
        cookies = st.text_area(
            "Instagram Cookies",
            placeholder="Paste your Instagram cookies here if you are facing download issues.",
            help="To get cookies, use a browser extension like 'Cookie-Editor'. Export the cookies for 'instagram.com' in the Netscape format and paste the content here."
        )
        st.markdown("For more info on how to get cookies for yt-dlp, see [this guide](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).")

if video_source == "Instagram Reel":
    video_url = st.text_input("Paste Instagram Reel URL:")
else:
    video_url = st.text_input("Paste YouTube Video URL:")

def clean_instagram_url(url):
    """Clean Instagram URL to remove tracking parameters"""
    # Remove tracking parameters
    url = re.sub(r'\?.*$', '', url)
    # Ensure it's a proper Instagram URL
    if not url.endswith('/'):
        url += '/'
    return url

def download_video(url, output_file, is_instagram=False, max_retries=3, cookies=None):
    """Download video with specific options based on source"""
    if is_instagram:
        url = clean_instagram_url(url)
        st.info(f"Cleaned URL: {url}")

    cookie_file = None
    if is_instagram and cookies:
        try:
            # Create a temporary file to store cookies
            cookie_file = f"cookies_{uuid.uuid4()}.txt"
            with open(cookie_file, "w", encoding="utf-8") as f:
                f.write(cookies)
            st.info("Using provided cookies for download.")
        except Exception as e:
            st.warning(f"Could not create cookie file: {e}")
            cookie_file = None

    for attempt in range(max_retries):
        try:
            if is_instagram:
                # Base command parts
                base_command = [
                    "yt-dlp", "--no-playlist", "--no-warnings", "--retries", "10",
                    "--fragment-retries", "10", "--file-access-retries", "10",
                    "--extractor-retries", "10", "--verbose", "--no-check-certificate"
                ]

                if cookie_file:
                    base_command.extend(["--cookies", cookie_file])
                else:
                    # If no cookies, we are not logged in
                    base_command.extend(["--extractor-args", "instagram:logged_in=false"])
                
                common_end = ["-f", "best[ext=mp4]/best", "-o", output_file, url]

                # Try different download methods for Instagram
                methods = [
                    # Method 1: Standard approach
                    base_command + [
                        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "--add-header", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "--add-header", "Accept-Language: en-US,en;q=0.5",
                        "--add-header", "Connection: keep-alive",
                        "--add-header", "Upgrade-Insecure-Requests: 1",
                    ] + common_end,
                    # Method 2: Alternative approach
                    base_command + [
                        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
                    ] + common_end
                ]
                
                # Try each method until one works
                for method_num, command in enumerate(methods, 1):
                    st.info(f"Trying download method {method_num}...")
                    try:
                        result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            check=True,
                            encoding='utf-8',
                            errors='replace'
                        )
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            if cookie_file and os.path.exists(cookie_file):
                                os.remove(cookie_file)
                            return True
                    except subprocess.CalledProcessError as e:
                        st.warning(f"Method {method_num} failed: {e.stderr}")
                        continue
                
                st.error("All download methods failed")
                if cookie_file and os.path.exists(cookie_file):
                    os.remove(cookie_file)
                return False
                
            else:
                # YouTube specific options
                command = [
                    "yt-dlp",
                    "--no-playlist",
                    "--no-warnings",
                    "--verbose",
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
            elif "Sign in" in error_msg or "login required" in error_msg:
                st.error("This video requires authentication. Please use the 'Advanced Options' to provide your Instagram cookies.")
            elif "Unable to download webpage" in error_msg:
                st.error("Could not access the video. Please check if the URL is correct and the video is public.")
            return False
            
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            if cookie_file and os.path.exists(cookie_file):
                os.remove(cookie_file)
            return False
    
    if cookie_file and os.path.exists(cookie_file):
        os.remove(cookie_file)
    return False

def ensure_ffmpeg():
    """
    Check if ffmpeg is available in PATH, if not, try to find it in the local repo folder.
    This supports both Render deployment (ffmpeg in PATH) and local execution.
    """
    if shutil.which("ffmpeg"):
        # ffmpeg is in PATH, which is the case on Render after installing it via packages.txt
        return

    # If not in PATH, check for local ffmpeg (for local development)
    ffmpeg_dir = os.path.join(os.path.dirname(__file__), "ffmpeg", "bin")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    
    if os.path.exists(ffmpeg_exe):
        # Add local ffmpeg to PATH
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
    else:
        st.error("ffmpeg not found. On Render, add 'ffmpeg' to your packages.txt. For local use, place it in the 'ffmpeg/bin' directory.")
        st.stop()

# Ensure ffmpeg is available before any video/audio processing
ensure_ffmpeg()

if video_url and st.button("Transcribe Video"):
    with st.spinner("Downloading video..."):
        unique_id = str(uuid.uuid4())
        output_file = f"video_{unique_id}.mp4"
        
        # Download the video
        is_instagram = video_source == "Instagram Reel"
        if not download_video(video_url, output_file, is_instagram, cookies=cookies):
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
