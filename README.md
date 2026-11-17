# Video Privacy Studio
React/Vite + Spring Boot 3 (Java 17) + Python/OpenCV video redaction.

## Requirements
- Java 17, Maven 3.9+, Node.js 20+, Python 3.10+, FFmpeg/ffprobe on PATH.
- Python: `python -m pip install -r processor/requirements.txt`

## Run (three terminals)
1. `cd backend && mvn spring-boot:run`
2. `cd frontend && npm install && npm run dev`
3. Open http://localhost:5173, upload an MP4, MOV, AVI or MKV and download the MP4.

The Spring Boot server invokes `python` (set `PYTHON_BIN` if needed). FFmpeg remuxes original audio when possible. Default max upload 200 MB. Processing is synchronous; long clips can take time. Video is processed locally and temporary uploads are deleted after processing. Completed files are retained in `backend/work/output` until manually deleted; do not expose this demo publicly without authentication, quotas, retention cleanup, and malware scanning.

## Detection limitations
Faces use OpenCV Haar cascades. Plates use OpenCV Russian-plate cascade plus a contour-based fallback for rectangular, high-contrast plates. Accuracy is **not guaranteed** (angles, motion, distance, lighting, non-Russian plate styles). Check all output before sharing. For production, use validated dedicated face and ANPR models and track detections across frames. Demo samples are synthetic and may not trigger all automatic detectors.

## Samples
`samples/demo-vehicle.mp4` and `samples/demo-face.mp4` are synthetic test videos created for this project, without real identities or real plate numbers. `samples/demo-vehicle.mp4` contains a moving plate-like region; `samples/demo-face.mp4` uses a cartoon face. The examples demonstrate uploading and MP4 output, but detection performance must be assessed separately on representative footage.

## API
`POST /api/videos/redact` multipart/form-data `file`, optional `faces` and `plates` booleans. Returns MP4 binary with `Content-Disposition` attachment. `GET /api/health` health response.
