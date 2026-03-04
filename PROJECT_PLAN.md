# AI Coach — Project Plan

**Standalone Android app. No backend. Privacy-first.**

## Overview

AI Coach analyzes exercise form using on-device pose estimation (MediaPipe) and provides coaching feedback via LLM APIs. Users bring their own API key. Everything runs on the phone.

## Architecture

```
┌─────────────────────────────────┐
│         Android App             │
│                                 │
│  Camera → MediaPipe Pose →      │
│  Extract joint angles/metrics → │
│  Build text prompt →            │
│  Call LLM API (user's key) →    │
│  Display coaching feedback      │
│                                 │
│  Local storage: SharedPrefs +   │
│  Room DB for session history    │
└─────────────────────────────────┘
          │
          │ HTTPS (user's API key)
          ▼
   OpenAI / Anthropic API
   (only text sent, no video)
```

**Key point:** Video never leaves the device. Only extracted pose metrics (joint angles, rep counts, timing) are sent as text to the LLM.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Kotlin |
| UI | Jetpack Compose |
| Pose Estimation | MediaPipe Pose Landmarker (on-device) |
| Camera | CameraX |
| LLM Integration | OkHttp → OpenAI/Anthropic REST API |
| Local Storage | Room DB + SharedPrefs |
| Build | Gradle + AGP |
| Min SDK | 26 (Android 8.0) |
| Distribution | Google Play Store |

## How It Works

### 1. Video Processing (On-Device)
- CameraX captures frames in real-time
- MediaPipe Pose Landmarker detects 33 body landmarks per frame
- App calculates: joint angles, body alignment, rep counting, tempo
- All processing happens on-device — no frames leave the phone

### 2. LLM Integration (User's API Key)
- User enters their OpenAI or Anthropic API key in Settings
- Key stored in EncryptedSharedPreferences
- After a set/exercise, app builds a text prompt:
  ```
  Exercise: Squat, 8 reps
  Avg knee angle at bottom: 78°, Hip hinge: 65°
  Tempo: 2.1s down, 1.8s up
  Issues: knees caving inward on reps 5-8
  
  Provide form coaching feedback.
  ```
- App calls LLM API directly via HTTPS
- Response displayed as coaching tips

### 3. No Accounts Needed
- No sign-up, no login
- Session history stored locally in Room DB
- User can export/clear their data anytime

## Features (MVP)

1. **Real-time pose overlay** — see skeleton on camera feed
2. **Rep counting** — automatic detection for common exercises
3. **Form analysis** — joint angle tracking per rep
4. **AI coaching** — LLM feedback after each set
5. **Exercise library** — squat, deadlift, push-up, pull-up, OHP
6. **Session history** — local log of workouts + feedback
7. **API key management** — support OpenAI + Anthropic, easy setup

## Features (Post-MVP)

- More exercises
- Video recording with pose overlay for review
- Progress tracking over time
- Custom exercise definitions
- Offline coaching (rule-based fallback when no API key)
- Wear OS companion (rep count on watch)

## Privacy

- **Video stays on device.** Always.
- Only derived metrics (angles, counts) sent to LLM as text
- API key encrypted locally
- No analytics, no tracking, no accounts
- User owns all their data

## Project Structure

```
app/
├── ui/              # Compose screens
│   ├── camera/      # Camera + pose overlay
│   ├── coaching/    # LLM feedback display
│   ├── history/     # Session log
│   └── settings/    # API key config
├── pose/            # MediaPipe integration
│   ├── PoseDetector.kt
│   ├── AngleCalculator.kt
│   └── RepCounter.kt
├── exercise/        # Exercise definitions + analysis
├── llm/             # API client (OpenAI/Anthropic)
│   ├── LlmClient.kt
│   ├── PromptBuilder.kt
│   └── ApiKeyStore.kt
├── data/            # Room DB + models
└── di/              # Hilt modules
```

## Development Phases

### Phase 1: Foundation (2 weeks)
- Project setup (Compose, CameraX, MediaPipe)
- Camera feed with real-time pose overlay
- Basic joint angle calculation

### Phase 2: Exercise Analysis (2 weeks)
- Rep counting for squat + push-up
- Form metrics extraction
- Exercise state machine

### Phase 3: LLM Integration (1 week)
- API key settings screen
- Prompt builder from exercise metrics
- OpenAI + Anthropic client
- Coaching feedback UI

### Phase 4: Polish + Launch (1 week)
- Session history
- Exercise library UI
- Play Store listing + screenshots
- Testing on multiple devices

**Total: ~6 weeks to MVP**

## Play Store Distribution

- Standard Play Store listing
- No special permissions beyond camera
- Privacy policy: "Video processed on-device only. Text metrics may be sent to OpenAI/Anthropic using your own API key."
- Free app, no IAP (users pay for their own API usage)
