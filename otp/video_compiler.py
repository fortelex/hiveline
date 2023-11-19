import cv2
import os
import re

def extract_frame_number(filename):
    # This regular expression finds numbers in the format '-frame-1234'
    match = re.search(r'-frame-(\d+)', filename)
    return int(match.group(1)) if match else 0

# Define the path to the images
image_folder = 'otp/output'
video_name = 'output_video.avi'

# Fetch all .png files and sort them by the frame number
images = [img for img in os.listdir(image_folder) if img.endswith(".png")]
images.sort(key=extract_frame_number)

# Determine the width and height from the first image
frame = cv2.imread(os.path.join(image_folder, images[0]))
height, width, layers = frame.shape

# Define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'XVID')
fps = 30  # Change FPS as needed
video = cv2.VideoWriter(video_name, fourcc, fps, (width, height))

for image in images:
    video.write(cv2.imread(os.path.join(image_folder, image)))

cv2.destroyAllWindows()
video.release()
