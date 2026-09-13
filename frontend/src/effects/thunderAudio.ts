/**
 * Procedural Web Audio API Thunder Synthesizer.
 *
 * Generates realistic acoustic rolling thunder without any external audio files.
 * Uses a resonant low-pass filtered pink noise burst with secondary reverberation
 * and sub-bass resonance to emulate real atmospheric thunder acoustics.
 */

class ThunderAudioEngine {
  private ctx: AudioContext | null = null;
  private enabled: boolean = false;
  private noiseBuffer: AudioBuffer | null = null;

  constructor() {
    // AudioContext is initialized lazily on first user interaction to comply
    // with browser autoplay policies.
  }

  private initContext() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
        this.noiseBuffer = this.createPinkNoiseBuffer(this.ctx, 4.0);
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      void this.ctx.resume();
    }
  }

  /** Generates 4 seconds of smooth pink noise for thunder synthesis. */
  private createPinkNoiseBuffer(ctx: AudioContext, durationSeconds: number): AudioBuffer {
    const bufferSize = Math.floor(ctx.sampleRate * durationSeconds);
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);

    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
      b6 = white * 0.115926;
    }
    return buffer;
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (enabled) {
      this.initContext();
    }
  }

  public isEnabled(): boolean {
    return this.enabled;
  }

  public toggle(): boolean {
    this.setEnabled(!this.enabled);
    return this.enabled;
  }

  /**
   * Triggers an acoustic thunder rumble.
   * @param intensity 0.1 to 1.0 (scales volume and duration)
   * @param isCloudToGround True if ground strike (sharper initial crack)
   * @param pan -1.0 (West/Left) to 1.0 (East/Right) for stereo spatialization
   */
  public play(intensity = 0.7, isCloudToGround = true, pan = 0) {
    if (!this.enabled) return;
    this.initContext();
    if (!this.ctx || !this.noiseBuffer) return;

    try {
      const now = this.ctx.currentTime;
      const duration = Math.min(3.5, 1.8 + intensity * 1.5);

      // Stereo panner for spatial thunder
      let pannerNode: StereoPannerNode | null = null;
      if (this.ctx.createStereoPanner) {
        pannerNode = this.ctx.createStereoPanner();
        pannerNode.pan.setValueAtTime(Math.max(-0.9, Math.min(0.9, pan)), now);
      }

      // Master gain node
      const masterGain = this.ctx.createGain();
      masterGain.gain.setValueAtTime(0.001, now);

      // 1. Initial thunder clap (sharp high-frequency transient if Cloud-to-Ground)
      if (isCloudToGround) {
        const clapSource = this.ctx.createBufferSource();
        clapSource.buffer = this.noiseBuffer;

        const clapFilter = this.ctx.createBiquadFilter();
        clapFilter.type = 'bandpass';
        clapFilter.frequency.setValueAtTime(450, now);
        clapFilter.frequency.exponentialRampToValueAtTime(80, now + 0.12);
        clapFilter.Q.setValueAtTime(3.5, now);

        const clapGain = this.ctx.createGain();
        clapGain.gain.setValueAtTime(0.35 * intensity, now);
        clapGain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

        clapSource.connect(clapFilter);
        clapFilter.connect(clapGain);
        clapGain.connect(masterGain);
        clapSource.start(now);
        clapSource.stop(now + 0.3);
      }

      // 2. Rolling deep sub-bass thunder rumble
      const rumbleSource = this.ctx.createBufferSource();
      rumbleSource.buffer = this.noiseBuffer;

      // Resonant Low-Pass filter that sweeps downwards like rolling thunder
      const rumbleFilter = this.ctx.createBiquadFilter();
      rumbleFilter.type = 'lowpass';
      rumbleFilter.frequency.setValueAtTime(180, now);
      rumbleFilter.frequency.exponentialRampToValueAtTime(35, now + duration);
      rumbleFilter.Q.setValueAtTime(4.5, now);

      // Rumble volume envelope
      const rumbleGain = this.ctx.createGain();
      const peakTime = now + (isCloudToGround ? 0.08 : 0.25);
      rumbleGain.gain.setValueAtTime(0.001, now);
      rumbleGain.gain.linearRampToValueAtTime(0.65 * intensity, peakTime);
      // Secondary secondary rumble wave peak
      rumbleGain.gain.exponentialRampToValueAtTime(0.35 * intensity, now + duration * 0.45);
      rumbleGain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

      rumbleSource.connect(rumbleFilter);
      rumbleFilter.connect(rumbleGain);
      rumbleGain.connect(masterGain);

      // Connect to output with stereo panning
      if (pannerNode) {
        masterGain.connect(pannerNode);
        pannerNode.connect(this.ctx.destination);
      } else {
        masterGain.connect(this.ctx.destination);
      }

      rumbleSource.start(now);
      rumbleSource.stop(now + duration + 0.1);
    } catch {
      // Gracefully ignore any browser audio context interruptions
    }
  }
}

export const thunderAudio = new ThunderAudioEngine();
