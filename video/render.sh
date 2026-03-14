#!/bin/bash
set -e

cd "$(dirname "$0")"
mkdir -p out

echo "Rendering MP4..."
npx remotion render src/index.ts ScoutDemo \
  --output out/scout-demo.mp4 \
  --codec h264 \
  --crf 18

echo "Converting to WebM..."
ffmpeg -y -i out/scout-demo.mp4 \
  -c:v libvpx-vp9 -crf 30 -b:v 0 \
  -an \
  out/scout-demo.webm

echo ""
echo "Done!"
echo "  MP4:  out/scout-demo.mp4"
echo "  WebM: out/scout-demo.webm"
