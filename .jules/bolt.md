## 2024-04-04 - Frame-by-Frame Face Tracking Optimization
**Learning:** Running MediaPipe face tracking on every single frame in moviepy is extremely expensive and causes a severe performance bottleneck.
**Action:** Implement memoization/caching by tracking the face only periodically (e.g., every 0.5 seconds) and reusing the last known face position (X coordinate) for the intermediate frames. This dramatically speeds up autocropping without a noticeable drop in tracking quality.
