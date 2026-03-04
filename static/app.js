/* ── AI Coach — Frontend ──────────────────────────────────────── */

// State
let strokeTypes = [];
let currentReport = '';
let currentStrokeType = '';
let currentVideoPath = '';
let selectedPerson = { ref: null, student: null };

// Browser-side video state
let _videoElements = { ref: null, student: null };
let _processedData = { ref: null, student: null };

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-links a').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      navigate(a.dataset.page);
    });
  });

  loadStrokeTypes();
  loadSettings();
  refreshSidebarStatus();
});

// ── Navigation ───────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelector(`[data-page="${page}"]`).classList.add('active');

  if (page === 'history') loadHistory();
  if (page === 'references') refreshRefList();
  if (page === 'analyze') checkAnalyzeReady();
}

// ── Toast notifications ──────────────────────────────────────────
function toast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── API helpers ──────────────────────────────────────────────────
async function api(method, url, body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) {
    const msg = data.detail || data.message || 'Request failed';
    throw new Error(msg);
  }
  return data;
}

// ── Sidebar status ───────────────────────────────────────────────
async function refreshSidebarStatus() {
  try {
    const settings = await api('GET', '/api/settings');
    const apiEl = document.getElementById('status-api');
    if (settings.api_key) {
      apiEl.textContent = `API key ···${settings.api_key_masked}`;
      apiEl.className = 'status-badge status-ok';
    } else {
      apiEl.textContent = 'No API key';
      apiEl.className = 'status-badge status-warn';
    }

    const refs = await api('GET', '/api/references');
    const refEl = document.getElementById('status-refs');
    const n = refs.references.length;
    refEl.textContent = `${n} reference${n !== 1 ? 's' : ''}`;
    refEl.className = n > 0 ? 'status-badge status-ok' : 'status-badge status-info';
  } catch (e) { /* silent */ }
}

// ── Stroke types ─────────────────────────────────────────────────
async function loadStrokeTypes() {
  try {
    const data = await api('GET', '/api/stroke-types');
    strokeTypes = data.types;
  } catch (e) { /* silent */ }
}

// ── Handle video file (local — no upload) ────────────────────────
function handleVideoFile(fileInput, target) {
  const file = fileInput.files[0];
  if (!file) return;

  const pathInputId = target === 'ref' ? 'ref-video-path' : 'student-video-path';
  document.getElementById(pathInputId).value = file.name;

  // Create object URL and hidden video element
  const objectUrl = URL.createObjectURL(file);
  _createVideoElement(target, objectUrl);

  toast(`Loaded ${file.name}`, 'success');
  fileInput.value = '';
}

function _createVideoElement(target, src) {
  // Clean up old element
  if (_videoElements[target]) {
    URL.revokeObjectURL(_videoElements[target].src);
    _videoElements[target].remove();
  }

  const video = document.createElement('video');
  video.src = src;
  video.preload = 'auto';
  video.muted = true;
  video.playsInline = true;
  video.style.display = 'none';
  video.crossOrigin = 'anonymous';
  document.body.appendChild(video);
  _videoElements[target] = video;

  return new Promise((resolve, reject) => {
    video.addEventListener('loadedmetadata', () => resolve(video), { once: true });
    video.addEventListener('error', () => reject(new Error('Failed to load video')), { once: true });
  });
}

// ── YouTube download ─────────────────────────────────────────────
async function downloadYouTube(target) {
  const urlInput = document.getElementById(`${target}-youtube-url`);
  const url = urlInput.value.trim();
  if (!url) { toast('Paste a YouTube URL first', 'error'); return; }

  const btn = document.getElementById(`btn-yt-${target}`);
  const pathInput = document.getElementById(target === 'ref' ? 'ref-video-path' : 'student-video-path');
  const progressEl = document.getElementById(`${target}-upload-progress`);
  const fillEl = document.getElementById(`${target}-upload-fill`);
  const labelEl = document.getElementById(`${target}-upload-label`);

  btn.disabled = true;
  btn.textContent = 'Downloading...';
  progressEl.style.display = 'block';
  fillEl.style.width = '0%';
  labelEl.textContent = 'Downloading from YouTube...';

  fillEl.style.width = '30%';
  const pulse = setInterval(() => {
    const cur = parseInt(fillEl.style.width);
    fillEl.style.width = (cur >= 90 ? 30 : cur + 5) + '%';
  }, 500);

  try {
    const data = await api('POST', '/api/youtube-download', { url });
    clearInterval(pulse);
    fillEl.style.width = '100%';
    labelEl.textContent = `Downloaded: ${data.filename}`;
    pathInput.value = data.filename;
    urlInput.value = '';

    // Stream video back from server for local processing
    await _createVideoElement(target, `/api/video/${encodeURIComponent(data.filename)}`);

    toast(`Downloaded: ${data.filename}`, 'success');
    setTimeout(() => { progressEl.style.display = 'none'; }, 2000);
  } catch (e) {
    clearInterval(pulse);
    progressEl.style.display = 'none';
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="margin-right:4px;vertical-align:middle"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31.7 31.7 0 0 0 0 12a31.7 31.7 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31.7 31.7 0 0 0 24 12a31.7 31.7 0 0 0-.5-5.8zM9.6 15.6V8.4l6.3 3.6-6.3 3.6z"/></svg> Download`;
  }
}

// ── Preview people (local) ───────────────────────────────────────
async function previewPeople(target, frameIdx) {
  const videoEl = _videoElements[target];
  if (!videoEl) { toast('Please select a video file', 'error'); return; }

  const btnId = target === 'ref' ? 'btn-preview-ref' : 'btn-preview-student';
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.textContent = 'Scanning...';

  try {
    // Wait for video metadata
    if (!videoEl.duration) {
      await new Promise((resolve, reject) => {
        videoEl.addEventListener('loadedmetadata', resolve, { once: true });
        videoEl.addEventListener('error', reject, { once: true });
      });
    }

    const duration = videoEl.duration;
    const totalFrames = Math.round(duration * 30); // Estimate at 30fps
    const frameTime = frameIdx !== undefined ? frameIdx / 30 : 1.0; // Default ~1s in

    const data = await previewPeopleLocal(target, videoEl, Math.min(frameTime, duration - 0.1));

    const selectPanel = document.getElementById(`${target}-player-select`);
    const optionsEl = document.getElementById(`${target}-player-options`);
    selectPanel.style.display = 'block';

    // Set up the frame slider
    const slider = document.getElementById(`${target}-frame-slider`);
    const sliderLabel = document.getElementById(`${target}-frame-label`);
    slider.max = totalFrames - 1;
    const currentFrame = frameIdx !== undefined ? frameIdx : 30;
    slider.value = currentFrame;
    sliderLabel.textContent = `Frame ${currentFrame} / ${totalFrames}`;

    const colors = ['#00ff00', '#ff6400', '#0064ff', '#ff00ff', '#00ffff'];

    if (data.numPeople <= 1) {
      selectedPerson[target] = null;
      optionsEl.innerHTML = `
        <div class="player-only-one">
          ${data.numPeople === 0 ? 'No people detected. Try a different frame or check the video.' : 'Only one person detected — will track automatically.'}
        </div>`;
    } else {
      selectedPerson[target] = 0;
      optionsEl.innerHTML = data.centers.map((c, i) => `
        <button class="player-option ${i === 0 ? 'selected' : ''}"
                data-idx="${i}" onclick="selectPerson('${target}', ${i}, this)">
          <span class="color-dot" style="background:${colors[i % colors.length]}"></span>
          Person ${i + 1}
        </button>
      `).join('');
      toast(`Found ${data.numPeople} people — select the player to track`, 'info');
    }
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Preview & Select Player';
  }
}

// ── Frame scrubber ────────────────────────────────────────────────
let _scrubTimer = {};

function scrubFrame(target, value) {
  const frameIdx = parseInt(value);
  const label = document.getElementById(`${target}-frame-label`);
  const slider = document.getElementById(`${target}-frame-slider`);
  label.textContent = `Frame ${frameIdx} / ${slider.max}`;

  clearTimeout(_scrubTimer[target]);
  _scrubTimer[target] = setTimeout(() => {
    previewPeople(target, frameIdx);
  }, 300);
}

function selectPerson(target, idx, btn) {
  selectedPerson[target] = idx;
  const container = document.getElementById(`${target}-player-options`);
  container.querySelectorAll('.player-option').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
}

// ── Detect strokes (browser-side processing) ─────────────────────
async function detectStrokes(target) {
  const videoEl = _videoElements[target];
  if (!videoEl) { toast('Please select a video file', 'error'); return; }

  const btnId = target === 'ref' ? 'btn-detect-ref' : 'btn-detect-student';
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.textContent = 'Processing...';

  const progressEl = document.getElementById(`${target}-progress`);
  const fillEl = document.getElementById(`${target}-progress-fill`);
  const labelEl = document.getElementById(`${target}-progress-label`);
  progressEl.style.display = 'block';
  fillEl.style.width = '0%';
  labelEl.textContent = 'Processing video in browser...';

  try {
    // Step 1: Process video locally with MediaPipe JS
    const result = await processVideoInBrowser(
      videoEl,
      selectedPerson[target],
      (current, total) => {
        const pct = Math.min(100, Math.round(current / total * 100));
        fillEl.style.width = pct + '%';
        labelEl.textContent = `Processing frame ${current}/${total}...`;
      }
    );

    _processedData[target] = result;

    // Step 2: Send landmarks to server for segmentation + classification
    labelEl.textContent = 'Analyzing strokes...';
    fillEl.style.width = '100%';

    const data = await api('POST', '/api/process-landmarks', {
      target,
      landmarks: result.landmarks,
      angles: result.angles,
      fps: result.fps,
      total_frames: result.total_frames,
      frame_step: result.frame_step,
      width: result.width,
      height: result.height,
    });

    // Step 3: Generate thumbnails locally
    labelEl.textContent = 'Generating thumbnails...';
    for (const stroke of data.strokes) {
      if (stroke.mid_frame_time !== undefined) {
        const midIdx = Math.floor(stroke.mid_frame_time * result.total_frames / videoEl.duration);
        const lm = midIdx < result.landmarks.length ? result.landmarks[midIdx] : null;
        stroke.thumbnail = await generateThumbnail(videoEl, stroke.mid_frame_time, lm);
      }
    }

    labelEl.textContent = `Done — ${data.num_strokes} strokes detected`;
    setTimeout(() => { progressEl.style.display = 'none'; }, 1500);

    renderStrokes(target, data);
    toast(`Detected ${data.num_strokes} strokes`, 'success');

    if (target === 'student') {
      currentVideoPath = document.getElementById('student-video-path').value;
    }
    refreshSidebarStatus();

  } catch (e) {
    progressEl.style.display = 'none';
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Detect Strokes';
  }
}

// ── Render strokes ───────────────────────────────────────────────
function renderStrokes(target, data) {
  const reviewEl = document.getElementById(`${target}-review`);
  const gridEl = document.getElementById(`${target}-strokes`);
  const countEl = document.getElementById(`${target}-stroke-count`);
  const infoEl = document.getElementById(`${target}-video-info`);

  reviewEl.style.display = 'block';
  countEl.textContent = `${data.num_strokes} strokes`;
  infoEl.textContent = `${data.total_frames} frames @ ${data.fps} fps`;

  gridEl.innerHTML = '';
  data.strokes.forEach(s => {
    const card = document.createElement('div');
    card.className = `stroke-card${s.discarded ? ' discarded' : ''}`;
    card.id = `stroke-${target}-${s.id}`;

    const opts = strokeTypes
      .filter(t => t.value !== 'unknown')
      .map(t => `<option value="${t.value}" ${t.value === s.final_label ? 'selected' : ''}>${t.label}</option>`)
      .join('');

    card.innerHTML = `
      <img src="${s.thumbnail || ''}" alt="Stroke ${s.id}" class="stroke-thumb">
      <div class="stroke-info">
        <select onchange="relabelStroke('${target}', ${s.id}, this.value)">${opts}</select>
        <div class="stroke-meta">
          Auto: ${s.stroke_type} (${Math.round(s.confidence * 100)}%)<br>
          Frames ${s.start_frame}–${s.end_frame} · ${s.duration}s
        </div>
        <div class="stroke-actions">
          <button class="btn btn-sm ${s.discarded ? 'btn-accent' : 'btn-danger'}"
                  onclick="toggleDiscard('${target}', ${s.id})">
            ${s.discarded ? 'Restore' : 'Discard'}
          </button>
        </div>
      </div>
    `;
    gridEl.appendChild(card);
  });

  if (target === 'ref') {
    showRefBuild(data);
  } else {
    showCompareSection(data);
  }
}

async function relabelStroke(target, strokeId, newLabel) {
  try {
    await api('POST', '/api/relabel', { target, stroke_id: strokeId, new_label: newLabel });
  } catch (e) { toast(e.message, 'error'); }
}

async function toggleDiscard(target, strokeId) {
  try {
    const data = await api('POST', '/api/discard', { target, stroke_id: strokeId });
    const card = document.getElementById(`stroke-${target}-${strokeId}`);
    if (data.discarded) {
      card.classList.add('discarded');
      card.querySelector('.btn').textContent = 'Restore';
      card.querySelector('.btn').className = 'btn btn-sm btn-accent';
    } else {
      card.classList.remove('discarded');
      card.querySelector('.btn').textContent = 'Discard';
      card.querySelector('.btn').className = 'btn btn-sm btn-danger';
    }
  } catch (e) { toast(e.message, 'error'); }
}

// ── Reference build ──────────────────────────────────────────────
function showRefBuild(data) {
  const buildEl = document.getElementById('ref-build');
  buildEl.style.display = 'block';

  const counts = {};
  data.strokes.filter(s => !s.discarded).forEach(s => {
    const label = s.final_label;
    counts[label] = (counts[label] || 0) + 1;
  });

  const countsEl = document.getElementById('ref-type-counts');
  countsEl.innerHTML = Object.entries(counts)
    .map(([type, count]) => {
      const display = strokeTypes.find(t => t.value === type)?.label || type;
      return `<span class="badge" style="margin-right:0.5rem">${display}: ${count}</span>`;
    }).join('');
}

async function buildReferences() {
  const btn = document.getElementById('btn-build-refs');
  btn.disabled = true;
  btn.textContent = 'Building...';

  try {
    const data = await api('POST', '/api/build-references');
    toast(`Built ${data.built} reference profile(s)`, 'success');
    document.getElementById('ref-build-result').innerHTML =
      `<div class="callout callout-success" style="margin-top:0.75rem">
        Built ${data.built} profile(s): ${data.profiles.map(p => p.display).join(', ')}
      </div>`;
    refreshSidebarStatus();
    refreshRefList();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Build & Save Profiles';
  }
}

// ── Reference management ─────────────────────────────────────────
function switchRefTab(tab) {
  document.querySelectorAll('#page-references .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#page-references .tab-content').forEach(t => t.classList.remove('active'));
  document.getElementById(`ref-tab-${tab}`).classList.add('active');
  event.target.classList.add('active');
  if (tab === 'manage') refreshRefList();
}

async function refreshRefList() {
  try {
    const data = await api('GET', '/api/references');
    const el = document.getElementById('ref-list');

    if (data.references.length === 0) {
      el.innerHTML = '<div class="callout callout-info">No reference profiles saved yet.</div>';
      return;
    }

    el.innerHTML = data.references.map(r => `
      <div class="ref-item">
        <div>
          <div class="ref-name">${r.display}</div>
          <div class="ref-meta">${r.sport} · ${r.num_samples} sample(s)</div>
        </div>
        <button class="btn btn-sm btn-danger" onclick="deleteRef('${r.sport}','${r.stroke_type}')">Delete</button>
      </div>
    `).join('');
  } catch (e) { /* silent */ }
}

async function deleteRef(sport, strokeType) {
  if (!confirm('Delete this reference profile?')) return;
  try {
    await api('DELETE', `/api/references/${sport}/${strokeType}`);
    toast('Reference deleted', 'success');
    refreshRefList();
    refreshSidebarStatus();
  } catch (e) { toast(e.message, 'error'); }
}

// ── Analyze: check ready ─────────────────────────────────────────
async function checkAnalyzeReady() {
  try {
    const refs = await api('GET', '/api/references');
    const warnEl = document.getElementById('analyze-no-refs');
    const mainEl = document.getElementById('analyze-main');
    if (refs.references.length === 0) {
      warnEl.style.display = 'block';
      mainEl.style.display = 'none';
    } else {
      warnEl.style.display = 'none';
      mainEl.style.display = 'block';
    }
  } catch (e) { /* silent */ }
}

// ── Compare section ──────────────────────────────────────────────
function showCompareSection(data) {
  const section = document.getElementById('student-compare-section');
  section.style.display = 'block';

  const select = document.getElementById('compare-stroke-select');
  select.innerHTML = '';

  data.strokes.filter(s => !s.discarded).forEach(s => {
    const display = strokeTypes.find(t => t.value === s.final_label)?.label || s.final_label;
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = `#${s.id}: ${display} (frames ${s.start_frame}–${s.end_frame})`;
    select.appendChild(opt);
  });
}

async function compareStroke() {
  const strokeId = parseInt(document.getElementById('compare-stroke-select').value);
  if (isNaN(strokeId)) { toast('Select a stroke', 'error'); return; }

  const btn = document.getElementById('btn-compare');
  btn.disabled = true;
  btn.textContent = 'Comparing...';

  try {
    const data = await api('POST', '/api/compare', { stroke_id: strokeId });

    currentReport = data.report;
    currentStrokeType = data.stroke_type;

    document.getElementById('compare-results').style.display = 'block';

    // Generate snapshot locally
    const snapshotCanvas = document.getElementById('compare-snapshot');
    const videoEl = _videoElements['student'];
    if (videoEl && data.mid_frame_idx !== undefined) {
      const processedData = _processedData['student'];
      const frameTime = data.mid_frame_idx / (processedData ? processedData.fps : 15);
      await seekTo(videoEl, Math.min(frameTime, videoEl.duration - 0.1));

      const ctx = snapshotCanvas.getContext('2d');
      const w = videoEl.videoWidth;
      const h = videoEl.videoHeight;
      snapshotCanvas.width = w;
      snapshotCanvas.height = h;
      ctx.drawImage(videoEl, 0, 0, w, h);

      // Draw skeleton if we have landmarks
      if (processedData && data.mid_frame_idx < processedData.landmarks.length) {
        const lm = processedData.landmarks[data.mid_frame_idx];
        if (lm) drawSkeleton(ctx, lm, w, h, '#00cc00', 2);
      }
    }

    // Top issues
    renderTopIssues(data.top_issues);

    // Phase charts
    renderPhaseCharts(data.charts);

    // Report
    document.getElementById('report-body').textContent = data.report;

    // Clear coaching
    document.getElementById('coaching-feedback').innerHTML = '';
    document.getElementById('btn-save-session').style.display = 'none';

    toast('Comparison complete', 'success');

  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Compare';
  }
}

function renderTopIssues(issues) {
  const el = document.getElementById('top-issues');
  if (!issues.length) {
    el.innerHTML = '<div class="callout callout-success">No significant differences — great form!</div>';
    return;
  }

  const jointNames = {
    right_shoulder: 'Shoulder angle',
    left_shoulder: 'Left shoulder',
    right_elbow: 'Elbow angle',
    left_elbow: 'Left elbow',
    right_hip: 'Hip angle',
    left_hip: 'Left hip',
    right_knee: 'Knee bend',
    left_knee: 'Left knee',
    hip_shoulder_separation: 'Hip-shoulder separation',
  };

  const phaseNames = {
    trophy: 'Trophy Position', racket_drop: 'Racket Drop', contact: 'Contact',
    follow_through: 'Follow-Through', ready: 'Ready', backswing: 'Backswing',
    forward_swing: 'Forward Swing', split_step: 'Split Step',
    racket_prep: 'Racket Prep', recovery: 'Recovery',
  };

  el.innerHTML = issues.map((issue, i) => {
    const rankClass = i < 1 ? 'rank-1' : i < 2 ? 'rank-2' : i < 3 ? 'rank-3' : 'rank-other';
    return `
      <div class="issue-item">
        <div class="issue-rank ${rankClass}">${i + 1}</div>
        <div class="issue-detail">
          <div class="issue-joint">${jointNames[issue.joint] || issue.joint}</div>
          <div class="issue-desc">at ${phaseNames[issue.phase] || issue.phase} · Student ${issue.student_avg}° vs Pro ${issue.pro_avg}°</div>
        </div>
        <div class="issue-diff" style="color: ${issue.diff > 15 ? 'var(--danger)' : 'var(--warn)'}">${issue.diff}° ${issue.direction}</div>
      </div>
    `;
  }).join('');
}

// ── Phase charts (Chart.js) ──────────────────────────────────────
const chartInstances = [];

function renderPhaseCharts(charts) {
  chartInstances.forEach(c => c.destroy());
  chartInstances.length = 0;

  const container = document.getElementById('phase-charts');
  container.innerHTML = '';

  charts.forEach(phase => {
    const section = document.createElement('div');
    section.className = 'phase-section';

    const phaseName = phase.phase.replace(/_/g, ' ');
    section.innerHTML = `<div class="phase-name">${phaseName}</div><div class="chart-row" id="charts-${phase.phase}"></div>`;
    container.appendChild(section);

    const row = section.querySelector('.chart-row');

    phase.joints.slice(0, 3).forEach(j => {
      const wrap = document.createElement('div');
      wrap.className = 'chart-container';
      const canvas = document.createElement('canvas');
      wrap.appendChild(canvas);
      row.appendChild(wrap);

      const labels = j.student.map((_, i) => i);
      const chart = new Chart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Student',
              data: j.student,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59,130,246,0.08)',
              fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
            },
            {
              label: 'Pro',
              data: j.pro,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16,185,129,0.08)',
              fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: {
              display: true,
              text: j.joint.replace(/_/g, ' '),
              font: { size: 12, weight: '600' },
              color: '#64748b',
            },
            legend: {
              labels: { boxWidth: 12, font: { size: 11 } },
            },
          },
          scales: {
            x: { display: false },
            y: {
              grid: { color: 'rgba(0,0,0,0.04)' },
              ticks: { font: { size: 10 } },
            },
          },
        },
      });
      chartInstances.push(chart);
    });
  });
}

// ── AI Coaching ──────────────────────────────────────────────────
async function getCoaching() {
  if (!currentReport) { toast('Run a comparison first', 'error'); return; }

  const btn = document.getElementById('btn-coaching');
  const loadingEl = document.getElementById('coaching-loading');
  const feedbackEl = document.getElementById('coaching-feedback');

  btn.disabled = true;
  loadingEl.style.display = 'flex';
  feedbackEl.innerHTML = '';

  try {
    const data = await api('POST', '/api/coaching', { report: currentReport });
    feedbackEl.innerHTML = marked.parse(data.feedback);
    document.getElementById('btn-save-session').style.display = 'inline-flex';
    window._lastFeedback = data.feedback;
    toast('Coaching feedback ready', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    loadingEl.style.display = 'none';
  }
}

async function saveSession() {
  try {
    await api('POST', '/api/sessions', {
      video_path: currentVideoPath,
      stroke_type: currentStrokeType,
      comparison_report: currentReport,
      coaching_feedback: window._lastFeedback || '',
    });
    toast('Session saved to history', 'success');
    document.getElementById('btn-save-session').style.display = 'none';
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ── Collapse helper ──────────────────────────────────────────────
function toggleCollapse(id) {
  const el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// ── History ──────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const data = await api('GET', '/api/sessions');
    const list = document.getElementById('history-list');
    const emptyEl = document.getElementById('history-empty');

    if (!data.sessions.length) {
      list.innerHTML = '';
      emptyEl.style.display = 'block';
      return;
    }

    emptyEl.style.display = 'none';
    list.innerHTML = data.sessions.map(s => `
      <div class="history-card">
        <div class="history-header" onclick="toggleHistory(this)">
          <span class="arrow">▶</span>
          <span class="timestamp">${s.timestamp}</span>
          <span class="stroke-type">${s.display_label}</span>
          <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); deleteSession(${s.id}, this)">Delete</button>
        </div>
        <div class="history-body">
          <div class="tabs">
            <button class="tab active" onclick="switchHistoryTab(this, 'feedback-${s.id}', 'report-${s.id}')">Coaching Feedback</button>
            <button class="tab" onclick="switchHistoryTab(this, 'report-${s.id}', 'feedback-${s.id}')">Comparison Report</button>
          </div>
          <div id="feedback-${s.id}" class="coaching-text">${marked.parse(s.coaching_feedback)}</div>
          <div id="report-${s.id}" class="report-text" style="display:none">${escapeHtml(s.comparison_report)}</div>
        </div>
      </div>
    `).join('');
  } catch (e) { toast(e.message, 'error'); }
}

function toggleHistory(header) {
  const body = header.nextElementSibling;
  const arrow = header.querySelector('.arrow');
  body.classList.toggle('open');
  arrow.classList.toggle('open');
}

function switchHistoryTab(btn, showId, hideId) {
  btn.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(showId).style.display = 'block';
  document.getElementById(hideId).style.display = 'none';
}

async function deleteSession(id, btn) {
  if (!confirm('Delete this session?')) return;
  try {
    await api('DELETE', `/api/sessions/${id}`);
    btn.closest('.history-card').remove();
    toast('Session deleted', 'success');
  } catch (e) { toast(e.message, 'error'); }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Settings ─────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const data = await api('GET', '/api/settings');
    if (data.api_key) {
      document.getElementById('api-key-status').innerHTML =
        `<span style="color:var(--accent)">Key set (···${data.api_key_masked})</span>`;
    }
    document.getElementById('settings-dominant').value = data.dominant_side;

    const modelSelect = document.getElementById('settings-model');
    if (modelSelect.options.length === 0) {
      const opt = document.createElement('option');
      opt.value = data.selected_model;
      opt.textContent = data.selected_model;
      modelSelect.appendChild(opt);
    }
    document.getElementById('model-status').innerHTML =
      `Current: <code>${data.selected_model}</code>`;
  } catch (e) { /* silent */ }
}

async function saveApiKey() {
  const key = document.getElementById('settings-api-key').value.trim();
  if (!key) { toast('Enter an API key', 'error'); return; }
  try {
    await api('POST', '/api/settings', { api_key: key });
    document.getElementById('api-key-status').innerHTML =
      `<span style="color:var(--accent)">Key saved (···${key.slice(-4)})</span>`;
    document.getElementById('settings-api-key').value = '';
    toast('API key saved', 'success');
    refreshSidebarStatus();
  } catch (e) { toast(e.message, 'error'); }
}

async function fetchModels() {
  try {
    const data = await api('GET', '/api/models');
    const select = document.getElementById('settings-model');
    select.innerHTML = '';
    data.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name}`;
      select.appendChild(opt);
    });
    select.addEventListener('change', async () => {
      await api('POST', '/api/settings', { selected_model: select.value });
      document.getElementById('model-status').innerHTML =
        `Current: <code>${select.value}</code>`;
      toast('Model updated', 'success');
    });
    toast(`Found ${data.models.length} models`, 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function saveManualModel() {
  const model = document.getElementById('settings-model-manual').value.trim();
  if (!model) return;
  try {
    await api('POST', '/api/settings', { selected_model: model });
    document.getElementById('model-status').innerHTML =
      `Current: <code>${model}</code>`;
    document.getElementById('settings-model-manual').value = '';
    toast('Model set', 'success');
  } catch (e) { toast(e.message, 'error'); }
}

async function saveDominant() {
  const val = document.getElementById('settings-dominant').value;
  try {
    await api('POST', '/api/settings', { dominant_side: val });
  } catch (e) { /* silent */ }
}
