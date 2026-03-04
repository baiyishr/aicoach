/* ── Pose Engine — Browser-side MediaPipe processing ─────────── */

// ── Landmark constants (mirror pose/landmarks.py) ──────────────
const LM = {
  NOSE: 0,
  LEFT_EYE_INNER: 1, LEFT_EYE: 2, LEFT_EYE_OUTER: 3,
  RIGHT_EYE_INNER: 4, RIGHT_EYE: 5, RIGHT_EYE_OUTER: 6,
  LEFT_EAR: 7, RIGHT_EAR: 8,
  MOUTH_LEFT: 9, MOUTH_RIGHT: 10,
  LEFT_SHOULDER: 11, RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13, RIGHT_ELBOW: 14,
  LEFT_WRIST: 15, RIGHT_WRIST: 16,
  LEFT_PINKY: 17, RIGHT_PINKY: 18,
  LEFT_INDEX: 19, RIGHT_INDEX: 20,
  LEFT_THUMB: 21, RIGHT_THUMB: 22,
  LEFT_HIP: 23, RIGHT_HIP: 24,
  LEFT_KNEE: 25, RIGHT_KNEE: 26,
  LEFT_ANKLE: 27, RIGHT_ANKLE: 28,
  LEFT_HEEL: 29, RIGHT_HEEL: 30,
  LEFT_FOOT_INDEX: 31, RIGHT_FOOT_INDEX: 32,
  NUM_LANDMARKS: 33,
};

const POSE_CONNECTIONS = [
  // Torso
  [LM.LEFT_SHOULDER, LM.RIGHT_SHOULDER],
  [LM.LEFT_SHOULDER, LM.LEFT_HIP],
  [LM.RIGHT_SHOULDER, LM.RIGHT_HIP],
  [LM.LEFT_HIP, LM.RIGHT_HIP],
  // Left arm
  [LM.LEFT_SHOULDER, LM.LEFT_ELBOW],
  [LM.LEFT_ELBOW, LM.LEFT_WRIST],
  // Right arm
  [LM.RIGHT_SHOULDER, LM.RIGHT_ELBOW],
  [LM.RIGHT_ELBOW, LM.RIGHT_WRIST],
  // Left leg
  [LM.LEFT_HIP, LM.LEFT_KNEE],
  [LM.LEFT_KNEE, LM.LEFT_ANKLE],
  // Right leg
  [LM.RIGHT_HIP, LM.RIGHT_KNEE],
  [LM.RIGHT_KNEE, LM.RIGHT_ANKLE],
];

// ── Angle computation (port of pose/angles.py) ─────────────────

function angleBetweenPoints(a, b, c) {
  // Angle at b formed by a-b-c, returns degrees [0, 180]
  const ba = [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const bc = [c[0] - b[0], c[1] - b[1], c[2] - b[2]];
  const dot = ba[0]*bc[0] + ba[1]*bc[1] + ba[2]*bc[2];
  const magBA = Math.sqrt(ba[0]*ba[0] + ba[1]*ba[1] + ba[2]*ba[2]);
  const magBC = Math.sqrt(bc[0]*bc[0] + bc[1]*bc[1] + bc[2]*bc[2]);
  let cosAngle = dot / (magBA * magBC + 1e-8);
  cosAngle = Math.max(-1, Math.min(1, cosAngle));
  return Math.acos(cosAngle) * (180 / Math.PI);
}

function computeJointAngles(landmarks) {
  // landmarks: array of 33 [x,y,z] — returns dict matching Python compute_joint_angles
  const L = LM;
  const angles = {};

  // Elbow angles
  angles.left_elbow = angleBetweenPoints(
    landmarks[L.LEFT_SHOULDER], landmarks[L.LEFT_ELBOW], landmarks[L.LEFT_WRIST]);
  angles.right_elbow = angleBetweenPoints(
    landmarks[L.RIGHT_SHOULDER], landmarks[L.RIGHT_ELBOW], landmarks[L.RIGHT_WRIST]);

  // Shoulder angles
  angles.left_shoulder = angleBetweenPoints(
    landmarks[L.LEFT_HIP], landmarks[L.LEFT_SHOULDER], landmarks[L.LEFT_ELBOW]);
  angles.right_shoulder = angleBetweenPoints(
    landmarks[L.RIGHT_HIP], landmarks[L.RIGHT_SHOULDER], landmarks[L.RIGHT_ELBOW]);

  // Hip angles
  angles.left_hip = angleBetweenPoints(
    landmarks[L.LEFT_SHOULDER], landmarks[L.LEFT_HIP], landmarks[L.LEFT_KNEE]);
  angles.right_hip = angleBetweenPoints(
    landmarks[L.RIGHT_SHOULDER], landmarks[L.RIGHT_HIP], landmarks[L.RIGHT_KNEE]);

  // Knee angles
  angles.left_knee = angleBetweenPoints(
    landmarks[L.LEFT_HIP], landmarks[L.LEFT_KNEE], landmarks[L.LEFT_ANKLE]);
  angles.right_knee = angleBetweenPoints(
    landmarks[L.RIGHT_HIP], landmarks[L.RIGHT_KNEE], landmarks[L.RIGHT_ANKLE]);

  // Hip-shoulder separation (atan2-based, 2D only)
  const hipVec = [
    landmarks[L.RIGHT_HIP][0] - landmarks[L.LEFT_HIP][0],
    landmarks[L.RIGHT_HIP][1] - landmarks[L.LEFT_HIP][1],
  ];
  const shoulderVec = [
    landmarks[L.RIGHT_SHOULDER][0] - landmarks[L.LEFT_SHOULDER][0],
    landmarks[L.RIGHT_SHOULDER][1] - landmarks[L.LEFT_SHOULDER][1],
  ];
  const hipAngle = Math.atan2(hipVec[1], hipVec[0]);
  const shoulderAngle = Math.atan2(shoulderVec[1], shoulderVec[0]);
  angles.hip_shoulder_separation = (shoulderAngle - hipAngle) * (180 / Math.PI);

  // Round all to 2 decimals
  for (const k in angles) angles[k] = Math.round(angles[k] * 100) / 100;

  return angles;
}

// ── Helpers ─────────────────────────────────────────────────────

function poseToArray(poseLandmarks) {
  // Convert MediaPipe JS PoseLandmark list to [[x,y,z], ...] rounded to 4 decimals
  const arr = [];
  for (let i = 0; i < poseLandmarks.length; i++) {
    const lm = poseLandmarks[i];
    arr.push([
      Math.round(lm.x * 10000) / 10000,
      Math.round(lm.y * 10000) / 10000,
      Math.round(lm.z * 10000) / 10000,
    ]);
  }
  return arr;
}

function hipCenter(landmarks) {
  return [
    (landmarks[LM.LEFT_HIP][0] + landmarks[LM.RIGHT_HIP][0]) / 2,
    (landmarks[LM.LEFT_HIP][1] + landmarks[LM.RIGHT_HIP][1]) / 2,
  ];
}

function pickClosestPose(allPoses, anchor) {
  // Pick pose closest to anchor by hip-center distance
  const anchorCenter = hipCenter(anchor);
  let bestIdx = 0, bestDist = Infinity;
  for (let i = 0; i < allPoses.length; i++) {
    const center = hipCenter(allPoses[i]);
    const dx = center[0] - anchorCenter[0];
    const dy = center[1] - anchorCenter[1];
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (dist < bestDist) { bestDist = dist; bestIdx = i; }
  }
  return bestIdx;
}

function waitForSeek(video, timeoutMs = 3000) {
  return new Promise((resolve) => {
    // Already at the right time and not seeking — done immediately
    if (!video.seeking) { resolve(); return; }
    const timer = setTimeout(() => {
      video.removeEventListener('seeked', onSeeked);
      resolve(); // Resolve anyway on timeout to avoid hanging
    }, timeoutMs);
    function onSeeked() {
      clearTimeout(timer);
      resolve();
    }
    video.addEventListener('seeked', onSeeked, { once: true });
  });
}

function seekTo(video, time) {
  // Set currentTime and return a promise that resolves when the seek completes
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      video.removeEventListener('seeked', onSeeked);
      resolve();
    }, 3000);
    function onSeeked() {
      clearTimeout(timer);
      resolve();
    }
    video.addEventListener('seeked', onSeeked, { once: true });
    video.currentTime = time;
  });
}

// ── Skeleton drawing on canvas ──────────────────────────────────

function drawSkeleton(ctx, landmarks, w, h, color = '#00ff00', lineWidth = 2) {
  ctx.lineWidth = lineWidth;

  // Draw connections
  ctx.strokeStyle = color;
  for (const [start, end] of POSE_CONNECTIONS) {
    if (start < landmarks.length && end < landmarks.length) {
      const x1 = landmarks[start][0] * w;
      const y1 = landmarks[start][1] * h;
      const x2 = landmarks[end][0] * w;
      const y2 = landmarks[end][1] * h;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
  }

  // Draw landmarks
  const dotRadius = 3;
  ctx.fillStyle = color;
  for (let i = 0; i < Math.min(LM.NUM_LANDMARKS, landmarks.length); i++) {
    const x = landmarks[i][0] * w;
    const y = landmarks[i][1] * h;
    ctx.beginPath();
    ctx.arc(x, y, dotRadius, 0, 2 * Math.PI);
    ctx.fill();
  }
}

// ── MediaPipe initialization ────────────────────────────────────

// Separate cached instances for IMAGE and VIDEO modes to avoid
// constant GL context teardown/rebuild when switching modes.
let _videoLandmarker = null;
let _videoLandmarkerNumPoses = 0;
let _imageLandmarker = null;
let _visionFileset = null;

const _MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task";

async function _getFileset() {
  if (!_visionFileset) {
    _visionFileset = await window.FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
    );
  }
  return _visionFileset;
}

async function _getVideoLandmarker(numPoses = 1) {
  if (_videoLandmarker && _videoLandmarkerNumPoses === numPoses) return _videoLandmarker;
  if (_videoLandmarker) { _videoLandmarker.close(); _videoLandmarker = null; }

  const vision = await _getFileset();
  _videoLandmarker = await window.PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: _MODEL_URL, delegate: "GPU" },
    runningMode: "VIDEO",
    numPoses: numPoses,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });
  _videoLandmarkerNumPoses = numPoses;
  return _videoLandmarker;
}

async function _getImageLandmarker() {
  if (_imageLandmarker) return _imageLandmarker;

  const vision = await _getFileset();
  _imageLandmarker = await window.PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: _MODEL_URL, delegate: "GPU" },
    runningMode: "IMAGE",
    numPoses: 5,
    minPoseDetectionConfidence: 0.3,
    minPosePresenceConfidence: 0.3,
  });
  return _imageLandmarker;
}

// ── Process video in browser ────────────────────────────────────

const TARGET_PROCESS_FPS = 15;

async function processVideoInBrowser(videoEl, personIdx, progressCb) {
  // Play video and process frames via requestVideoFrameCallback.
  // This gives actual sequential decoded frames — no seek imprecision.
  const duration = videoEl.duration;
  const w = videoEl.videoWidth;
  const h = videoEl.videoHeight;

  const frameInterval = 1.0 / TARGET_PROCESS_FPS;
  const totalProcessFrames = Math.floor(duration / frameInterval);

  const multiPerson = personIdx !== null && personIdx !== undefined;
  const numPoses = multiPerson ? 5 : 1;
  const landmarker = await _getVideoLandmarker(numPoses);

  const allLandmarks = [];
  const allAngles = [];
  let prevTracked = null;
  let processedCount = 0;
  let lastProcessedTime = -Infinity;

  // Use requestVideoFrameCallback if available, fallback to timeupdate
  const hasRVFC = 'requestVideoFrameCallback' in HTMLVideoElement.prototype;

  return new Promise((resolve, reject) => {
    function processCurrentFrame() {
      const currentTime = videoEl.currentTime;
      // Skip if too close to last processed frame (enforce ~15fps)
      if (currentTime - lastProcessedTime < frameInterval * 0.8) return;
      lastProcessedTime = currentTime;

      const timestampMs = Math.round(currentTime * 1000);
      let result;
      try {
        result = landmarker.detectForVideo(videoEl, timestampMs);
      } catch (e) {
        allLandmarks.push(null);
        allAngles.push(null);
        processedCount++;
        return;
      }

      if (result.landmarks && result.landmarks.length > 0) {
        const allPoses = result.landmarks.map(p => poseToArray(p));
        let chosen;

        if (multiPerson && allPoses.length > 1) {
          if (prevTracked) {
            chosen = pickClosestPose(allPoses, prevTracked);
          } else {
            chosen = Math.min(personIdx, allPoses.length - 1);
          }
        } else if (multiPerson && personIdx !== null) {
          chosen = Math.min(personIdx, allPoses.length - 1);
        } else {
          chosen = 0;
        }

        const lm = allPoses[chosen];
        prevTracked = lm;
        allLandmarks.push(lm);
        allAngles.push(computeJointAngles(lm));
      } else {
        allLandmarks.push(null);
        allAngles.push(null);
      }

      processedCount++;
      if (progressCb && processedCount % 5 === 0) {
        progressCb(processedCount, totalProcessFrames);
      }
    }

    function onEnded() {
      cleanup();
      if (progressCb) progressCb(processedCount, processedCount);
      resolve({
        landmarks: allLandmarks,
        angles: allAngles,
        fps: processedCount / duration,  // Actual effective fps
        total_frames: processedCount,
        frame_step: 1,
        width: w,
        height: h,
      });
    }

    let rvfcHandle = null;
    let timeupdateHandler = null;

    function scheduleNextFrame() {
      rvfcHandle = videoEl.requestVideoFrameCallback((now, metadata) => {
        processCurrentFrame();
        if (!videoEl.ended && !videoEl.paused) scheduleNextFrame();
      });
    }

    function cleanup() {
      videoEl.removeEventListener('ended', onEnded);
      if (hasRVFC && rvfcHandle !== null) {
        videoEl.cancelVideoFrameCallback(rvfcHandle);
      }
      if (timeupdateHandler) {
        videoEl.removeEventListener('timeupdate', timeupdateHandler);
      }
      videoEl.pause();
    }

    videoEl.addEventListener('ended', onEnded, { once: true });

    // Start from the beginning
    videoEl.currentTime = 0;
    videoEl.muted = true;
    // Play at 2x speed to process faster (frames still render correctly)
    videoEl.playbackRate = 2.0;

    if (hasRVFC) {
      videoEl.play().then(() => scheduleNextFrame()).catch(reject);
    } else {
      // Fallback: use timeupdate (less precise, ~4 events/sec at 1x)
      timeupdateHandler = () => processCurrentFrame();
      videoEl.addEventListener('timeupdate', timeupdateHandler);
      videoEl.playbackRate = 1.0; // timeupdate is too sparse at 2x
      videoEl.play().catch(reject);
    }
  });
}

// ── Preview people (local, IMAGE mode) ──────────────────────────

async function previewPeopleLocal(target, videoEl, frameTime) {
  // Detect all people at a specific time, draw skeletons on canvas
  const landmarker = await _getImageLandmarker();

  await seekTo(videoEl, frameTime);

  const result = landmarker.detect(videoEl);

  const canvas = document.getElementById(`${target}-preview-canvas`);
  const ctx = canvas.getContext('2d');
  const w = videoEl.videoWidth;
  const h = videoEl.videoHeight;
  canvas.width = w;
  canvas.height = h;

  // Draw video frame
  ctx.drawImage(videoEl, 0, 0, w, h);

  const colors = ['#00ff00', '#ff6400', '#0064ff', '#ff00ff', '#00ffff'];
  const poses = [];
  const centers = [];

  if (result.landmarks && result.landmarks.length > 0) {
    for (let i = 0; i < result.landmarks.length; i++) {
      const lm = poseToArray(result.landmarks[i]);
      poses.push(lm);
      centers.push(hipCenter(lm));

      // Draw skeleton
      const color = colors[i % colors.length];
      drawSkeleton(ctx, lm, w, h, color, 2);

      // Draw person label
      const cx = Math.round(centers[i][0] * w);
      const cy = Math.round(centers[i][1] * h);
      const label = `Person ${i + 1}`;
      ctx.font = '16px sans-serif';
      const metrics = ctx.measureText(label);
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(cx - 4, cy - 18, metrics.width + 8, 24);
      ctx.fillStyle = color;
      ctx.fillText(label, cx, cy);
    }
  }

  return { poses, centers, numPeople: poses.length };
}

// ── Generate thumbnail from video ───────────────────────────────

async function generateThumbnail(videoEl, timeSeconds, landmarks) {
  // Seek to time, draw frame + optional skeleton, return data URI
  await seekTo(videoEl, timeSeconds);

  const canvas = document.createElement('canvas');
  const w = videoEl.videoWidth;
  const h = videoEl.videoHeight;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(videoEl, 0, 0, w, h);

  if (landmarks) {
    drawSkeleton(ctx, landmarks, w, h, '#00cc00', 2);
  }

  return canvas.toDataURL('image/jpeg', 0.7);
}
