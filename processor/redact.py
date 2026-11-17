import argparse
import subprocess
import sys
from pathlib import Path
import cv2


def blur_region(frame, x, y, w, h):
    height, width = frame.shape[:2]
    pad = max(4, int(min(w, h) * 0.14))
    x1, y1 = max(0, x-pad), max(0, y-pad)
    x2, y2 = min(width, x+w+pad), min(height, y+h+pad)
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    k = max(31, (min(roi.shape[:2]) // 2) | 1)
    frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)


def plate_candidates(frame, cascade):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found = list(cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3,
                                          minSize=(35, 12))) if not cascade.empty() else []
    # Conservative fallback for high-contrast rectangular plate-like objects.
    edges = cv2.Canny(gray, 80, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = cw / max(1, ch)
        if not (2.2 <= aspect <= 5.8 and 42 <= cw <= w * .65 and 13 <= ch <= h * .22):
            continue
        if cv2.contourArea(c) < 0.35 * cw * ch:
            continue
        crop = gray[y:y+ch, x:x+cw]
        if crop.std() < 35:
            continue
        found.append((x, y, cw, ch))
    # Merge overlapping rectangles to avoid multiple blurs.
    result = []
    for box in sorted(found, key=lambda a: a[2]*a[3], reverse=True):
        x,y,bw,bh = map(int, box)
        if any(max(x,ox) < min(x+bw,ox+ow) and max(y,oy) < min(y+bh,oy+oh)
               for ox,oy,ow,oh in result):
            continue
        result.append((x,y,bw,bh))
    return result[:15]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--faces', choices=['true','false'], default='true')
    parser.add_argument('--plates', choices=['true','false'], default='true')
    args = parser.parse_args()
    input_file = Path(args.input)
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(input_file))
    if not cap.isOpened():
        raise RuntimeError('Cannot open video input')
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 240:
        fps = 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width < 1 or height < 1:
        raise RuntimeError('Invalid video dimensions')
    intermediate = output_file.with_name(output_file.stem + '.silent.mp4')
    writer = cv2.VideoWriter(str(intermediate), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width,height))
    if not writer.isOpened():
        raise RuntimeError('Cannot create output video')
    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    plate_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_russian_plate_number.xml')
    frames = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if args.faces == 'true':
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                for x,y,w,h in face_detector.detectMultiScale(gray, 1.1, 4, minSize=(28,28)):
                    blur_region(frame, int(x),int(y),int(w),int(h))
            if args.plates == 'true':
                for x,y,w,h in plate_candidates(frame, plate_detector):
                    blur_region(frame,x,y,w,h)
            writer.write(frame)
            frames += 1
    finally:
        cap.release()
        writer.release()
    if frames == 0:
        raise RuntimeError('Video contains no readable frames')
    # Re-encode for browser-friendly H.264 when available; copy original audio if present.
    cmd = ['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(intermediate),
           '-i',str(input_file),'-map','0:v:0','-map','1:a?','-c:v','libx264',
           '-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac',
           '-shortest','-movflags','+faststart',str(output_file)]
    try:
        subprocess.run(cmd, check=True)
    finally:
        intermediate.unlink(missing_ok=True)
    print(f'Processed {frames} frames', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Processing failed: {exc}', file=sys.stderr)
        sys.exit(1)
