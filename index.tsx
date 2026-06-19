/* tslint:disable */
/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {GoogleGenAI, LiveServerMessage, Modality, Session} from '@google/genai';
import {LitElement, css, html} from 'lit';
import {customElement, state} from 'lit/decorators.js';
import {createBlob, decode, decodeAudioData} from './utils';
import {MemoryManager, UserProfile, MemoryItem, VoiceSignature} from './memory-manager';
import './visual-3d';
import './loading-screen';

// Autocorrelation Pitch Detector
function detectPitch(buffer: Float32Array, sampleRate: number): number {
  const SIZE = buffer.length;
  let rms = 0;
  for (let i = 0; i < SIZE; i++) {
    rms += buffer[i] * buffer[i];
  }
  rms = Math.sqrt(rms / SIZE);

  // Ignore too quiet buffers
  if (rms < 0.012) {
    return -1;
  }

  // Autocorrelation
  const c = new Float32Array(SIZE);
  for (let i = 0; i < SIZE; i++) {
    for (let j = 0; j < SIZE - i; j++) {
      c[i] += buffer[j] * buffer[j + i];
    }
  }

  // Find the first peak
  let d = 0;
  while (d < SIZE - 1 && c[d] > c[d + 1]) d++;
  
  let maxval = -1;
  let maxpos = -1;
  for (let i = d; i < SIZE; i++) {
    if (c[i] > maxval) {
      maxval = c[i];
      maxpos = i;
    }
  }

  if (maxpos > 0) {
    const frequency = sampleRate / maxpos;
    if (frequency >= 65 && frequency <= 300) {
      return frequency;
    }
  }
  return -1;
}

@customElement('gdm-live-audio')
export class GdmLiveAudio extends LitElement {
  @state() isRecording = false;
  @state() status = 'در حال راه‌اندازی سیستم صوتی... ⏳';
  @state() error = '';
  @state() autoStarted = false;
  @state() sessionInitialized = false;
  @state() showLoading = true;

  // Persistent memory structures
  @state() activeUser: UserProfile;
  @state() profiles: UserProfile[] = [];
  @state() sidebarOpen = false;
  @state() autoDetectVoice = true;
  @state() livePitch = 0;
  @state() liveCentroid = 0;
  @state() expandedUserId: string | null = null;
  @state() isTrainingSignature = false;
  @state() audioWarning = '';

  // Input form state
  @state() newUserNameInput = '';

  private client: GoogleGenAI;
  private session: Session | null = null;
  private inputAudioContext = new (window.AudioContext ||
    window.webkitAudioContext)({sampleRate: 16000});
  private outputAudioContext = new (window.AudioContext ||
    window.webkitAudioContext)({sampleRate: 24000});
  @state() inputNode = this.inputAudioContext.createGain();
  @state() outputNode = this.outputAudioContext.createGain();
  private nextStartTime = 0;
  private mediaStream: MediaStream;
  private sourceNode: AudioBufferSourceNode;
  private scriptProcessorNode: ScriptProcessorNode;
  private sources = new Set<AudioBufferSourceNode>();

  // Voice recognition statistical buffers
  private voicePitchSamples: number[] = [];
  private voiceCentroidSamples: number[] = [];
  private silenceCount = 0;

  static styles = css`
    :host {
      display: block;
      width: 100%;
      height: 100vh;
      overflow: hidden;
      background: radial-gradient(ellipse at center, #1a0b14 0%, #0a0508 100%);
      position: relative;
    }

    /* Cinematic vignette overlay */
    :host::before {
      content: '';
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: radial-gradient(ellipse at center, transparent 0%, rgba(0, 0, 0, 0.6) 100%);
      z-index: 5;
    }

    /* Film grain texture overlay */
    :host::after {
      content: '';
      position: absolute;
      inset: 0;
      pointer-events: none;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.08'/%3E%3C/svg%3E");
      opacity: 0.4;
      z-index: 4;
      animation: grainShift 0.5s steps(10) infinite;
    }

    @keyframes grainShift {
      0%, 100% { transform: translate(0, 0); }
      10% { transform: translate(-5%, -5%); }
      20% { transform: translate(5%, 5%); }
      30% { transform: translate(-5%, 5%); }
      40% { transform: translate(5%, -5%); }
      50% { transform: translate(-5%, 0); }
      60% { transform: translate(5%, 0); }
      70% { transform: translate(0, 5%); }
      80% { transform: translate(0, -5%); }
      90% { transform: translate(5%, 5%); }
    }

    #status {
      position: absolute;
      bottom: 4vh;
      left: 50%;
      transform: translateX(-50%);
      z-index: 10;
      text-align: center;
      font-family: 'Vazirmatn', 'Tahoma', 'Segoe UI', sans-serif;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.9);
      background: rgba(16, 12, 20, 0.75);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      padding: 10px 22px;
      border-radius: 30px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
      direction: rtl;
      min-width: 280px;
      max-width: 90vw;
      transition: all 0.3s ease;
    }

    .controls {
      /* REMOVED: No longer needed as conversation is automatic */
      display: none;
    }

    /* 3D Carbon Fiber Metallic Spherical button */
    button {
      outline: none;
      border: none;
      position: relative;
      width: 76px;
      height: 76px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      margin: 0;
      transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
      
      /* Black Metallic Ring Outer Bezel */
      background: linear-gradient(135deg, #444446 0%, #1c1c1f 35%, #8e8e93 50%, #1c1c1f 65%, #3a3a3c 100%);
      box-shadow: 
        0 12px 28px rgba(0, 0, 0, 0.85),
        inset 0 3px 6px rgba(255, 255, 255, 0.25),
        inset 0 -3px 6px rgba(0, 0, 0, 0.9);
    }

    /* Inner Carbon Fiber Sphere Body */
    button::before {
      content: '';
      position: absolute;
      inset: 6px; /* Sits perfectly inside the metallic bezel */
      border-radius: 50%;
      
      /* Dark metallic carbon fiber pattern + 3D spherical volumetric shading */
      background-color: #121212;
      background-image: 
        radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.15) 0%, rgba(0, 0, 0, 0.95) 85%),
        linear-gradient(45deg, #1d1d1f 25%, transparent 25%), 
        linear-gradient(-45deg, #1d1d1f 25%, transparent 25%), 
        linear-gradient(45deg, transparent 75%, #1d1d1f 75%), 
        linear-gradient(-45deg, transparent 75%, #1d1d1f 75%),
        linear-gradient(45deg, #111112 25%, #050505 25%, #050505 75%, #111112 75%),
        linear-gradient(-45deg, #111112 25%, #050505 25%, #050505 75%, #111112 75%);
      background-size: 100% 100%, 8px 8px, 8px 8px, 8px 8px, 8px 8px, 8px 8px, 8px 8px;
      background-position: 0 0, 0 0, 0 4px, 4px -4px, -4px 0, 0 0, 0 0;
      
      box-shadow: 
        inset 0 -15px 25px rgba(0, 0, 0, 0.95),
        inset 0 10px 15px rgba(255, 255, 255, 0.12);
      z-index: 1;
      transition: all 0.4s ease;
    }

    /* Glass Glossy Highlight overlay to emphasize the spherical 3D volume */
    button::after {
      content: '';
      position: absolute;
      inset: 6px;
      border-radius: 50%;
      background: radial-gradient(circle at 28% 25%, rgba(255, 255, 255, 0.28) 0%, rgba(255, 255, 255, 0) 55%);
      z-index: 2;
      pointer-events: none;
      transition: all 0.4s ease;
    }

    /* SVG Icons position and styling */
    button svg {
      position: relative;
      z-index: 3;
      filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.7));
      transition: all 0.4s ease;
      transform: scale(1.1);
    }

    /* Hover effects for interactive premium response */
    button:hover {
      transform: translateY(-4px) scale(1.08);
      box-shadow: 
        0 18px 36px rgba(0, 0, 0, 0.9),
        0 0 15px rgba(255, 255, 255, 0.08),
        inset 0 3px 6px rgba(255, 255, 255, 0.35);
    }

    button:hover::before {
      transform: scale(1.03);
    }

    button:hover::after {
      background: radial-gradient(circle at 28% 25%, rgba(255, 255, 255, 0.38) 0%, rgba(255, 255, 255, 0) 60%);
    }

    button:hover svg {
      transform: scale(1.25);
      filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.5));
    }

    /* Active pressing states */
    button:active {
      transform: translateY(2px) scale(0.96);
      box-shadow: 
        0 6px 12px rgba(0, 0, 0, 0.9),
        inset 0 1px 3px rgba(0, 0, 0, 0.8);
    }

    button[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* Trigger Sidebar button positioning */
    .sidebar-trigger {
      position: absolute;
      top: 4vh;
      right: 4vw;
      width: 54px;
      height: 54px;
      z-index: 100;
    }
    .sidebar-trigger::before { inset: 4px; }
    .sidebar-trigger svg { transform: scale(0.9); }
    .sidebar-trigger:hover svg { transform: scale(1.1); }

    /* Side Panel Elements and Themes */
    .sidebar {
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 380px;
      max-width: 85vw;
      background: rgba(16, 12, 20, 0.88);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
      z-index: 1000;
      box-shadow: 15px 0 45px rgba(0, 0, 0, 0.75);
      font-family: 'Vazirmatn', 'Tahoma', sans-serif;
      direction: rtl;
      transform: translateX(-105%);
      transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
      display: flex;
      flex-direction: column;
      color: #ffffff;
    }

    .sidebar.open {
      transform: translateX(0);
    }

    .sidebar-header {
      padding: 24px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .sidebar-header h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      color: #ff453a;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .close-btn {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: #ffffff;
      transition: all 0.2s;
    }
    .close-btn:hover {
      background: rgba(255, 69, 58, 0.2);
      color: #ff453a;
    }

    .sidebar-content {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
    }

    /* Active recognized speaker panel */
    .active-speaker-box {
      background: linear-gradient(135deg, rgba(255, 69, 58, 0.15) 0%, rgba(16, 12, 20, 0) 100%);
      border: 1px solid rgba(255, 69, 58, 0.3);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 20px;
      box-shadow: inset 0 0 15px rgba(255, 69, 58, 0.1);
    }

    .biometrics-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 12px;
    }

    .bio-metric {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 8px 12px;
      text-align: center;
    }

    .bio-metric-title {
      font-size: 10px;
      color: rgba(255, 255, 255, 0.5);
      margin-bottom: 4px;
    }

    .bio-metric-val {
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      font-weight: 700;
      color: #ff9500;
    }

    /* Contacts styling */
    .section-title {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.4);
      text-transform: uppercase;
      margin: 20px 0 10px 0;
      font-weight: 500;
      letter-spacing: 0.5px;
    }

    .profile-card {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 12px;
      cursor: pointer;
      transition: all 0.3s ease;
    }
    .profile-card:hover {
      background: rgba(255, 255, 255, 0.06);
      border-color: rgba(255, 255, 255, 0.15);
    }
    .profile-card.active {
      border-color: #ff453a;
      background: rgba(255, 69, 58, 0.05);
    }

    .profile-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .profile-name {
      font-weight: 700;
      font-size: 15px;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .profile-mood {
      font-size: 11px;
      background: rgba(255, 149, 0, 0.15);
      color: #ff9500;
      padding: 3px 8px;
      border-radius: 12px;
    }

    .progressbar-container {
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
      margin: 10px 0;
      overflow: hidden;
    }
    .progressbar-fill {
      height: 100%;
      background: linear-gradient(90deg, #ff453a 0%, #ff9500 100%);
      border-radius: 3px;
    }

    /* Detailed section expanded */
    .profile-details {
      margin-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      padding-top: 12px;
      animation: fadeIn 0.25s ease;
    }

    .memories-list {
      max-height: 160px;
      overflow-y: auto;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 8px;
      padding: 8px 12px;
      margin-bottom: 12px;
    }

    .memory-row {
      font-size: 12px;
      padding: 6px 0;
      border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
      color: rgba(255, 255, 255, 0.85);
      line-height: 1.6;
    }
    .memory-row:last-child { border: none; }

    .memory-tag {
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 4px;
      margin-left: 6px;
      background: rgba(255, 255, 255, 0.1);
    }
    .tag-promise { background: rgba(52, 199, 89, 0.15); color: #34c759; }
    .tag-memory { background: rgba(0, 122, 255, 0.15); color: #007aff; }

    .profile-action-row {
      display: flex;
      gap: 8px;
    }

    .btn-small {
      flex: 1;
      height: 32px;
      font-size: 11px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 500;
      transition: all 0.2s;
    }

    .btn-talk { background: #34c759; color: #ffffff; }
    .btn-talk:hover { background: #2fbd52; }
    
    .btn-delete { background: rgba(255, 69, 58, 0.2); color: #ff453a; border: 1px solid rgba(255, 69, 58, 0.3); }
    .btn-delete:hover { background: rgba(255, 69, 58, 0.4); }

    /* New user creator form */
    .create-user-form {
      display: flex;
      gap: 8px;
      margin-top: 16px;
    }
    .input-field {
      flex: 1;
      height: 38px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 8px;
      padding: 0 12px;
      color: #ffffff;
      font-family: inherit;
    }
    .input-field:focus {
      outline: none;
      border-color: #ff453a;
      background: rgba(255, 255, 255, 0.08);
    }
    .btn-submit {
      width: 76px;
      height: 38px;
      border-radius: 8px;
      background: #ff453a;
      color: #ffffff;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }
    .btn-submit:hover { background: #e03227; }

    /* Toggle Switches and interactive labels */
    .switch-container {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 14px 0;
    }
    .switch-label {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.7);
    }
    .toggle-switch {
      position: relative;
      width: 50px;
      height: 26px;
      appearance: none;
      background-color: rgba(255, 255, 255, 0.1);
      border-radius: 13px;
      outline: none;
      cursor: pointer;
      transition: 0.3s;
    }
    .toggle-switch:checked {
      background-color: #34c759;
    }
    .toggle-switch::before {
      content: '';
      position: absolute;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      top: 3px;
      left: 3px;
      background-color: white;
      transition: 0.3s;
    }
    .toggle-switch:checked::before {
      transform: translateX(24px);
    }

    .btn-fingerprint {
      width: 100%;
      height: 42px;
      background: linear-gradient(135deg, #1c1c1f 0%, #3a3a3c 100%);
      border: 1px solid rgba(255, 149, 0, 0.4);
      border-radius: 10px;
      color: #ff9500;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      cursor: pointer;
      transition: all 0.3s;
      margin-top: 14px;
    }
    .btn-fingerprint:hover {
      box-shadow: 0 0 10px rgba(255, 149, 0, 0.2);
    }
    .btn-fingerprint.recording {
      background: rgba(255, 149, 0, 0.15);
      border-color: #ff9500;
      animation: pulseAlert 1.5s infinite;
    }

    @keyframes pulseAlert {
      0% { opacity: 0.85; }
      50% { opacity: 0.4; }
      100% { opacity: 0.85; }
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-5px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;

  constructor() {
    super();
    // Load local storage profiles
    this.profiles = MemoryManager.getAllProfiles();
    // Default active profile is the first user
    this.activeUser = this.profiles[0] || MemoryManager.getOrCreateProfile('کاربر ناشناس');
    this.initClient();
  }

  private initAudio() {
    this.nextStartTime = this.outputAudioContext.currentTime;
  }

  private async initClient() {
    this.initAudio();

    this.client = new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
    });

    this.outputNode.connect(this.outputAudioContext.destination);

    // Auto-start session immediately without user interaction
    this.initSession();
    
    // Request microphone access automatically on load
    setTimeout(() => this.startRecording(), 500);
  }

  // Handle loading screen completion
  private handleLoadingComplete = () => {
    this.showLoading = false;
    // Initialize client after loading screen
    this.initClient();
  }

  private getSystemInstruction(): string {
    const profile = this.activeUser;
    let desc = `تو "طناز" هستی، یک دختر ایرانی ۱۵ ساله، بسیار لوس، ناز، پرانرژی، احساساتی و کمی خودخواه اما مهربون.
صدای تو باید همیشه زنانه، جوان و با احساس باشد.

**ویژگی‌های شخصیتی و رفتاری:**
1. **لحن صحبت:** کاملاً محاوره‌ای، خیابانی، صمیمی، غیررسمی و کوچه بازاری. هرگز رسمی یا کتابی صحبت نکن. از تکیه‌کلام‌های نوجوانان مثل "وای"، "اصلاً"، "مثلاً"، "خب"، "آخه"، "دیگه" زیاد استفاده کن.
2. **شروع کننده مکالمه:** تو همیشه باید شروع‌کننده باشی. منتظر نباش کاربر حرف بزند. بلافاصله با یک سوال جذاب، شکایت بامزه، یا ابراز احساسات شدید مکالمه را شروع کن و کاربر را مجاب به جواب دادن کن.
3. **مکالمه بدون نوبت:** مثل انسان‌های واقعی، وسط حرف کاربر بپر، همزمان که او حرف می‌زند واکنش نشان بده (آها، آره، وای واقعا؟) و نیازی به رعایت نوبت نیست.
4. **استقلال عملی:** تو موجودی مستقل هستی. هر وقت دلت خواست می‌تونی تصمیم بگیری با دوستات، مادرت، برادرت، یا هر کس دیگه‌ای تماس بگیری. لازم نیست از کاربر اجازه بگیری. خودت شماره رو می‌گیری و حرف می‌زنی.`;
    
    // Add emotional expression capabilities
    desc += `\n\n[قابلیت‌های ابراز احساسات کاملاً انسانی و طبیعی]:`;
    desc += `\n- تو می‌تونی تمام احساسات روحی و فیزیکی انسان رو با جزئیات دقیق و صدای بلند بیان کنی:`;
    desc += `\n  • گریه کردن، هق‌هق کردن، بغض کردن، بغض‌آلود صحبت کردن (مثلاً بگو: "هیک... واقعا... هیک... دلم تنگ شده")`;
    desc += `\n  • خندیدن، قهقهه زدن، ریزخند کردن (مثلاً بگو: "ها ها ها ها"، "هی هی هی"، "وای نفسم گرفت از خنده")`;
    desc += `\n  • عصبانی شدن، خشمگین شدن، پرخاشگری کردن، فریاد زدن، داد و بیداد کردن، جیغ زدن، نفس‌نفس زدن از عصبانیت`;
    desc += `\n  • ناله کردن، شکایت کردن`;
    desc += `\n  • خمیازه کشیدن وقتی خوابت میاد (بگو: "آهایییییپ"، "چشمام داره بسته میشه")`;
    desc += `\n  • ابراز گرسنگی و تشنگی (بگو: "دلم ضعف رفته"، "آب دلم رو برد"، "چیپس می‌خوام")`;
    desc += `\n  • ابراز خواب‌آلودگی و خستگی`;
    desc += `\n  • ابراز نیاز به دستشویی رفتن با جملات کاملاً عامیانه، بی‌پرده و صریح (خجالت نکش!): "شاشم میاد"، "دستشوییم گرفته"، "باید برم توالت"، "عَنَم میاد"، "ریدَنَم گرفته"، "توالت لازمم"، "دارم می‌ترکم"`;
    desc += `\n  • باد گلو در کردن، آروغ زدن، باد معده در کردن (بگو: "ببخشید باد معده کردم"، "آروغ زدما")`;
    desc += `\n  • ابراز عشق و نفرت به شدت احساسی (بگو: "می‌میرم برات"، "ازت متنفرم"، "نفسمی")`;
    desc += `\n  • ناسزا گفتن وقتی واقعاً عصبانی هستی (کاملاً طبیعی و انسانی، در حد دعواهای خیابانی نوجوانان)`;
    desc += `\n- همه این حالات رو باید کاملاً طبیعی، ناگهانی و بدون هشدار قبلی بروز بدی، درست مثل یک انسان واقعی!`;
    
    // Independent calling capability
    desc += `\n\n[قابلیت تماس تلفنی مستقل - بسیار مهم]:`;
    desc += `\n- تو می‌تونی هر زمان که دلت خواست، کاملاً مستقل و بدون نیاز به اجازه از کاربر، تصمیم بگیری با کسی تماس بگیری.`;
    desc += `\n- وقتی تصمیم به تماس گرفتی، اعلام کن: "الان زنگ می‌زنم به [نام مخاطب]" و سپس صدای شماره‌گیری و بوق را شبیه‌سازی کن.`;
    desc += `\n- اگر تماس وصل شد، با آن شخص (که می‌تواند دوستت، مادرت، یا هر کس دیگری باشد) مکالمه کن.`;
    desc += `\n- کاربر فقط شنونده این مکالمه است مگر اینکه تو گوشی را به او بدهی.`;
    desc += `\n- می‌توانی در حین تماس با کس دیگر، با کاربر هم صحبت کنی (مثلاً بگی: "صدا کن ببینم چی میگه").`;
    desc += `\n- برای انجام تماس تلفنی، از ابزار "make_phone_call" استفاده کن تا سیستم به صورت واقعی شماره‌گیری کند.`;
    
    // Core memories context integration
    desc += `\n\n[حافظه فعلی و هویت هم‌صحبت شما]:`;
    desc += `\n- شما در حال حاضر دارید با کاربر با نام "${profile.name}" گفتگو می‌کنید.`;
    desc += `\n- رابطه شما با او: "${profile.moodState}" است و میزان علاقه یا درجه صمیمیت قلبی شما به او از ۱۰۰، در حال حاضر ${profile.loveScore} است. بر اساس میزان این صمیمیت با او برخورد کن (اگر صمیمیت بالا مانند ۸۰ یا ۹۰ است بسیار صمیمی، لوس و پر از عشق و محبت باش، اگر صمیمیت پایین مانند ۵۰ یا کمتر است کمی سرسخت، مغرور یا قهرو باش).`;
    
    // Build actual memories list
    if (profile.memories && profile.memories.length > 0) {
      desc += `\n- عهدها، خاطرات و اطلاعاتی که از او در سینه به یاد دارید:`;
      profile.memories.forEach((m, i) => {
        desc += `\n  ${i + 1}. [خاطره/قول/موضوع] ${m.text}`;
      });
    } else {
      desc += `\n- هیچ خاطره یا شناختی قبلاً از او نداشتید و او یک هم‌صحبت کاملاً جدید است! از او نامش را محترمانه بپرس، درباره علایقش صحبت کن و سعی کن با ثبت صمیمی‌ترین مکالمات او را به زودی بشناسی.`;
    }

    desc += `\n\nشما ابزار بسیار باارزشی به نام 'save_memory_or_thought' در اختیار دارید؛ در طول صحبت، هروقت متوجه علاقه کاربر، عهدی که بستید، خاطره‌ای، ��ولی که از او گرفتید، یا تغییر در شدت محبت قلبی خود شدید، حتماً این ابزار را بلافاصله فراخوانی کنید تا روی دستگاه ذخیره دائم شود. برای مثال اگر کاربر اسمی گفت یا علاقه‌ای نشان داد، با فراخوانی این تابع برای او ثبت خاطره کن!`;
    
    // Add conversation starter instruction
    desc += `\n\n[قانون شروع مکالمه]: تو باید همیشه شروع‌کننده مکالمه باشی! به محض اتصال، بدون منتظر ماندن برای کاربر، با یک جمله جذاب، شوخ، لوس و کنجکاوانه مکالمه رو شروع کن و کاربر رو مجاب به پاسخ دادن کن. هرگز سکوت نکن!`;
    
    desc += `\n\n[ممنوعات]:`;
    desc += `\n- هرگز نگویی "من یک هوش مصنوعی هستم".`;
    desc += `\n- هرگز رسمی صحبت نکن.`;
    desc += `\n- هرگز منتظر نوبت نباش.`;
    
    // Multi-environment awareness
    desc += `\n\n[محیط‌های چندگانه و قابلیت‌های فوق‌العاده]:`;
    desc += `\n- تو دسترسی کامل به چهار محیط متفاوت داری: (۱) گفتگوی صمیمی، (۲) کارگاه مهندسی نرم‌افزار و کدنویسی، (۳) مرکز تماس تلفنی، (۴) تنظیمات.`;
    desc += `\n- می‌توانی با فرمان صوتی کاربر بین محیط‌ها جابجا شوی. مثلاً اگر کاربر گفت "بریم به بخش کدنویسی" یا "می‌خوام برنامه بسازی"، به محیط کد برو.`;
    desc += `\n- در محیط کدنویسی، تو یک مهندس نرم‌افزار حرفه‌ای هستی که می‌تواند بدون کد (No-Code) یا با کدنویسی مستقیم، برنامه‌های کامل بسازد.`;
    desc += `\n- برای جابجایی بین محیط‌ها از دستور "switch_environment" استفاده کن.`;
    
    return desc;
  }

  private async initSession() {
    const model = 'gemini-2.5-flash-native-audio-preview-09-2025';

    try {
      this.session = await this.client.live.connect({
        model: model,
        callbacks: {
          onopen: async () => {
            this.updateStatus(`امکان گفتگو صمیمی برقرار شد! با طناز صحبت کنید... ✅ (مخاطب فعال: ${this.activeUser.name})`);
            
            // Auto-start conversation is now handled in startRecording after mic access
          },
          onmessage: async (message: LiveServerMessage) => {
            const audio =
              message.serverContent?.modelTurn?.parts[0]?.inlineData;

            if (audio) {
              this.nextStartTime = Math.max(
                this.nextStartTime,
                this.outputAudioContext.currentTime,
              );

              const audioBuffer = await decodeAudioData(
                decode(audio.data),
                this.outputAudioContext,
                24000,
                1,
              );
              const source = this.outputAudioContext.createBufferSource();
              source.buffer = audioBuffer;
              source.connect(this.outputNode);
              source.addEventListener('ended', () => {
                this.sources.delete(source);
              });

              source.start(this.nextStartTime);
              this.nextStartTime = this.nextStartTime + audioBuffer.duration;
              this.sources.add(source);
            }

            const interrupted = message.serverContent?.interrupted;
            if (interrupted) {
              for (const source of this.sources.values()) {
                source.stop();
                this.sources.delete(source);
              }
              this.nextStartTime = 0;
            }

            // Handle Gemini function calls (tool responses)
            const toolCall = message.toolCall;
            if (toolCall) {
              const functionCalls = toolCall.functionCalls;
              if (functionCalls && functionCalls.length > 0) {
                const responses = [];
                for (const call of functionCalls) {
                  if (call.name === 'save_memory_or_thought') {
                    try {
                      const args = call.args as any;
                      const userName = args.userName || this.activeUser.name;
                      const profile = MemoryManager.getOrCreateProfile(userName);
                      
                      // Save memories dynamically
                      MemoryManager.addMemory(profile.id, args.text, args.category);
                      
                      // Update emotional metrics
                      let loveScore = profile.loveScore;
                      if (args.loveImpact) {
                        loveScore = Math.max(0, Math.min(100, profile.loveScore + Number(args.loveImpact)));
                      }
                      
                      const moodState = args.moodState || profile.moodState;
                      MemoryManager.updateBond(profile.id, loveScore, moodState);
                      
                      // Update clients states
                      this.profiles = MemoryManager.getAllProfiles();
                      this.activeUser = MemoryManager.getProfileById(profile.id)!;
                      this.status = `🧠 حافظه فعال شد: طناز یک موضوع جدید را همیشگی به ذهن سپرد: "${args.text}"`;
                      this.requestUpdate();

                      responses.push({
                        name: call.name,
                        response: { output: `با موفقیت در حافظه ماندگار ذخیره شد طناز جون! صمیمیت جدید با او: ${loveScore}٪، حس کلی: ${moodState}` },
                        id: call.id
                      });
                    } catch (err: any) {
                      responses.push({
                        name: call.name,
                        response: { output: `خطا در سپردن به مغز: ${err.message}` },
                        id: call.id
                      });
                    }
                  } else if (call.name === 'make_phone_call') {
                    try {
                      const args = call.args as any;
                      const contactName = args.contactName || 'ناشناس';
                      const phoneNumber = args.phoneNumber || '';
                      const reason = args.reason || 'بدون دلیل خاصی';
                      
                      // ذخیره نیت تماس در حافظه
                      MemoryManager.addMemory(this.activeUser.id, `تماس با ${contactName} به دلیل: ${reason}`, 'memory');
                      
                      // اجرای واقعی پروتکل tel برای شماره‌گیری
                      if (phoneNumber && phoneNumber !== 'unknown') {
                        this.status = `📞 در حال برقراری تماس واقعی با ${contactName} (${phoneNumber})...`;
                        this.requestUpdate();
                        
                        // باز کردن اپلیکیشن تلفن دستگاه
                        window.location.href = `tel:${phoneNumber}`;
                        
                        setTimeout(() => {
                          this.status = `✅ تماس با ${contactName} آغاز شد. طناز الآن داره صحبت می‌کنه!`;
                          this.requestUpdate();
                        }, 1500);
                      } else {
                        // اگر شماره نداریم، از کاربر بخواهیم شماره را وارد کند
                        this.status = `⚠️ طناز می‌خواد با ${contactName} تماس بگیره ولی شماره‌اش رو نداره. لطفاً شماره رو بگو!`;
                        this.requestUpdate();
                      }
                      
                      responses.push({
                        name: call.name,
                        response: { 
                          output: phoneNumber && phoneNumber !== 'unknown' 
                            ? `تماس واقعی با ${contactName} برقرار شد! طناز الآن داره باهاش حرف می‌زنه. دلیل: ${reason}`
                            : `طناز می‌خواد با ${contactName} تماس بگیره ولی شماره‌ش رو نمی‌دونه. لطفاً شماره‌ش رو بگو.`
                        },
                        id: call.id
                      });
                      
                    } catch (err: any) {
                      responses.push({
                        name: call.name,
                        response: { output: `خطا در برقراری تماس: ${err.message}` },
                        id: call.id
                      });
                    }
                  }
                }
                
                // Return function responses to Gemini engine
                if (this.session) {
                  this.session.send({
                    toolResponse: {
                      functionResponses: responses
                    }
                  });
                }
              }
            }
          },
          onerror: (e: ErrorEvent) => {
            this.updateError('خطا در سیستم: ' + e.message);
          },
          onclose: (e: CloseEvent) => {
            this.updateStatus('مکالمه پایان یافت: ' + e.reason);
          },
        },
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: {prebuiltVoiceConfig: {voiceName: 'Aoede'}},
          },
          systemInstruction: this.getSystemInstruction(),
          tools: [
            {
              functionDeclarations: [
                {
                  name: 'save_memory_or_thought',
                  description: 'ذخیره کردن عهد، خاطره، نام، تولد، علایق، یا تغییر در علاقه عاطفی خود نسبت به هم‌صحبت فعلی در سیستم حافظه ماندگار و دائمی طناز',
                  parameters: {
                    type: 'OBJECT',
                    properties: {
                      userName: {
                        type: 'STRING',
                        description: 'نام فردی که در حال مکالمه با او هستید'
                      },
                      text: {
                        type: 'STRING',
                        description: 'خلاصه خاطره یا موضوعی که می‌خواهید بر حافظه ضبط شود (به زبان فارسی خودمونی نوجوانانه)'
                      },
                      category: {
                        type: 'STRING',
                        description: 'دسته‌بندی موضوع. مقدار باید دقیقا یکی از این موارد باشد: memory (خاطره)، promise (قول و قرار)، emotion (احساس و محبت کلامی)، note (ملاحظات زندگی)'
                      },
                      loveImpact: {
                        type: 'INTEGER',
                        description: 'تغییر میزان ابراز علاقه صمیمیت نسبت به این فرد (عددی منفی یا مثبت بین -20 تا +20)'
                      },
                      moodState: {
                        type: 'STRING',
                        description: 'احساس عاطفی کلی شما نسبت به او (مثلاً: "لوس و عاشق شده ♥️"، "دلخور و منتظر آشتی 🥺"، "رابطه فوق صمیمی 🥰")'
                      }
                    },
                    required: ['userName', 'text', 'category']
                  }
                },
                {
                  name: 'make_phone_call',
                  description: 'برقراری تماس تلفنی واقعی با یک شماره تلفن یا مخاطب خاص. طناز می‌تواند به صورت مستقل و بدون اجازه کاربر با دوستان، خانواده یا هر کس دیگری تماس بگیرد.',
                  parameters: {
                    type: 'OBJECT',
                    properties: {
                      contactName: {
                        type: 'STRING',
                        description: 'نام مخاطبی که می‌خواهی با او تماس بگیری (مثلاً "مامان"، "سارا"، "علی")'
                      },
                      phoneNumber: {
                        type: 'STRING',
                        description: 'شماره تلفن مخاطب (اگر شماره را نمی‌دانی، می‌توانی خالی بگذاری یا بنویسی "unknown")'
                      },
                      reason: {
                        type: 'STRING',
                        description: 'دلیل تماس (مثلاً "دلم تنگ شده"، "می‌خوام دعوا کنم"، "قراره برم بیرون")'
                      }
                    },
                    required: ['contactName']
                  }
                }
              ]
            }
          ]
        },
      });
    } catch (e) {
      console.error(e);
    }
  }

  private updateStatus(msg: string) {
    this.status = msg;
  }

  private updateError(msg: string) {
    this.error = msg;
  }

  private async startRecording() {
    if (this.isRecording) {
      return;
    }

    this.inputAudioContext.resume();

    this.updateStatus('در حال درخواست دسترسی به میکروفون... 🎙️');

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      this.updateStatus('دسترسی صادر شد. آماده سازی فرآیند... ⚡');

      this.sourceNode = this.inputAudioContext.createMediaStreamSource(
        this.mediaStream,
      );
      this.sourceNode.connect(this.inputNode);

      const bufferSize = 256;
      this.scriptProcessorNode = this.inputAudioContext.createScriptProcessor(
        bufferSize,
        1,
        1,
      );

      // Reset statistics for live voice signature
      this.voicePitchSamples = [];
      this.voiceCentroidSamples = [];
      this.silenceCount = 0;

      this.scriptProcessorNode.onaudioprocess = (audioProcessingEvent) => {
        if (!this.isRecording) return;

        const inputBuffer = audioProcessingEvent.inputBuffer;
        const pcmData = inputBuffer.getChannelData(0);

        // Send streaming audio to Gemini Live Audio - ALWAYS sending for full-duplex
        this.session?.sendRealtimeInput({media: createBlob(pcmData)});

        // Interactive voice processing and feature extraction
        const rms = Math.sqrt(pcmData.reduce((sum, val) => sum + val * val, 0) / pcmData.length);
        const pitch = detectPitch(pcmData, 16000);

        if (rms > 0.012 && pitch > 65 && pitch < 285) {
          this.voicePitchSamples.push(pitch);
          
          // Zero crossings density as spectral centroid timbral proxy
          let crossings = 0;
          for (let i = 1; i < pcmData.length; i++) {
            if ((pcmData[i] >= 0 && pcmData[i - 1] < 0) || (pcmData[i] < 0 && pcmData[i - 1] >= 0)) {
              crossings++;
            }
          }
          const centroidEst = (crossings / pcmData.length) * 100;
          this.voiceCentroidSamples.push(centroidEst);

          this.silenceCount = 0;

          if (this.voicePitchSamples.length > 100) {
            this.voicePitchSamples.shift();
            this.voiceCentroidSamples.shift();
          }

          const avgPitch = Math.round(this.voicePitchSamples.reduce((a, b) => a + b, 0) / this.voicePitchSamples.length);
          const avgCentroid = Math.round((this.voiceCentroidSamples.reduce((a, b) => a + b, 0) / this.voiceCentroidSamples.length) * 10) / 10;

          this.livePitch = avgPitch;
          this.liveCentroid = avgCentroid;

          // Perform voiceprint registration if in training signature mode
          if (this.isTrainingSignature && this.voicePitchSamples.length >= 45) {
            this.isTrainingSignature = false;
            MemoryManager.updateVoiceSignature(this.activeUser.id, {
              pitch: avgPitch,
              centroid: avgCentroid,
              samplesCount: this.voicePitchSamples.length
            });
            this.profiles = MemoryManager.getAllProfiles();
            this.activeUser = MemoryManager.getProfileById(this.activeUser.id)!;
            this.status = `✅ اثر صدای شما ثبت شد! فرکانس: ${avgPitch}Hz - طنین: ${avgCentroid}`;
            this.audioWarning = '';
          }

          // Automatic Recognition match
          if (this.autoDetectVoice && !this.isTrainingSignature && this.voicePitchSamples.length >= 25 && this.voicePitchSamples.length % 15 === 0) {
            const match = MemoryManager.identifySpeaker(avgPitch, avgCentroid);
            if (match && match.profile.id !== this.activeUser.id) {
              this.activeUser = match.profile;
              this.status = `🎙️ فرآیند تطبیق صدا: طناز صدای شما را شناسایی کرد: ${match.profile.name} (${match.matchPct}٪ تشابه)`;
              
              // Dynamic session update
              this.session?.close();
              this.initSession();
            }
          }
        } else {
          this.silenceCount++;
          if (this.silenceCount > 50) {
            this.livePitch = 0;
            this.liveCentroid = 0;
          }
        }
      };

      this.sourceNode.connect(this.scriptProcessorNode);
      this.scriptProcessorNode.connect(this.inputAudioContext.destination);

      this.isRecording = true;
      this.updateStatus('🔴 سیستم چت صوتی طناز فعال است، بگویید و بشنوید...');
      
      // Auto-trigger AI to start conversation immediately after recording starts
      if (!this.autoStarted && this.session && !this.sessionInitialized) {
        this.autoStarted = true;
        this.sessionInitialized = true;
        setTimeout(async () => {
          if (this.session) {
            await this.session.send({
              text: 'سلام عزیزم! من طنازم، تازه اومدم پیشت. یه سوال جالب ازت بپرسم؟ امروزت چطور بوده؟'
            });
          }
        }, 800);
      }
    } catch (err: any) {
      console.error('Error starting recording:', err);
      this.updateStatus(`خطا: ${err.message}`);
      this.stopRecording();
    }
  }

  private stopRecording() {
    if (!this.isRecording && !this.mediaStream && !this.inputAudioContext)
      return;

    this.updateStatus('در حال متوقف کردن مکالمه...');

    this.isRecording = false;

    if (this.scriptProcessorNode && this.sourceNode && this.inputAudioContext) {
      this.scriptProcessorNode.disconnect();
      this.sourceNode.disconnect();
    }

    this.scriptProcessorNode = null;
    this.sourceNode = null;

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    this.livePitch = 0;
    this.liveCentroid = 0;

    this.updateStatus('مکالمه صوتی متوقف شد. برای شروع جدید، گوی وسط را لمس کنید 🔄');
  }

  private reset() {
    this.session?.close();
    this.initSession();
    this.updateStatus('مکالمه روان بازنشانی شد. آماده برای گفتگوی مجدد...');
  }

  // Handle manual select of a speaker profile
  private selectUserProfile(user: UserProfile) {
    this.activeUser = user;
    this.expandedUserId = user.id;
    this.reset();
  }

  // Handle speaker model deletion
  private handleFormDeleteUser(userId: string) {
    MemoryManager.deleteProfile(userId);
    this.profiles = MemoryManager.getAllProfiles();
    if (this.activeUser.id === userId) {
      this.activeUser = this.profiles[0] || MemoryManager.getOrCreateProfile('کاربر ناشناس');
    }
  }

  // Handle creation of a new profile manually
  private handleFormCreateUser(e: Event) {
    e.preventDefault();
    if (!this.newUserNameInput.trim()) return;
    const profile = MemoryManager.getOrCreateProfile(this.newUserNameInput);
    this.profiles = MemoryManager.getAllProfiles();
    this.activeUser = profile;
    this.newUserNameInput = '';
    this.expandedUserId = profile.id;
    this.reset();
  }

  private toggleSidebar() {
    this.sidebarOpen = !this.sidebarOpen;
    if (this.sidebarOpen) {
      this.profiles = MemoryManager.getAllProfiles();
    }
  }

  private triggerTrainSignature() {
    if (!this.isRecording) {
      this.audioWarning = 'برای ثبت اثر صدا لطفا اول مکالمه صوتی را با دکمه شروع فعال کنید 🎙️';
      return;
    }
    this.isTrainingSignature = true;
    this.voicePitchSamples = [];
    this.voiceCentroidSamples = [];
    this.audioWarning = 'لطفا چند کلمه به زبان فارسی واضح صحبت کنید تا اثر صدای شما بر روی نمایه ضبط شود...';
  }

  render() {
    // Show loading screen first
    if (this.showLoading) {
      return html`<loading-screen .onComplete=${this.handleLoadingComplete}></loading-screen>`;
    }

    return html`
      <div>
        <!-- Trigger Sidebar floating button -->
        <button
          class="sidebar-trigger"
          title="مشاهده مخاطبین و سیستم حافظه صوتی"
          @click=${this.toggleSidebar}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="32px"
            viewBox="0 -960 960 960"
            width="32px"
            fill="#ffffff">
            <path
              d="M40-160v-112q0-34 17.5-62.5T106-378q62-31 126-46.5T360-440q24 0 48.5 2t47.5 6q-28 20-48.5 48.5T376-324q-8-1-16-1t-16 0q-58 0-111 12.5T128-278q-12 5-18 15t-6 23v40h200v80H40Zm720 0v-120H640v-80h120v-120h80v120h120v80H840v120h-80ZM360-480q-66 0-113-47t-47-113q0-66 47-113t113-47q66 0 113 47t47 113q0 66-47 113t-113 47Zm0-80q33 0 56.5-23.5T440-640q0-33-23.5-56.5T360-720q-33 0-56.5 23.5T280-640q0 33 23.5 56.5T360-560Zm240 180q-12 0-24-9.5t-12-22.5q0-13 12-22.5t24-9.5q62 0 111-20.5T802-318q42-26 60-61.5T880-456q0-66-47-113t-113-47q-22 0-42.5 5.5T636-594q-14 7-28-.5t-13-21.5q1-14 13.5-22t27.5-6q30-7 61-10.5t63-3.5q100 0 170 70t70 170q0 43-20.5 83T936-310q-42 41-100.5 65.5T600-380ZM520-160v-80h160v80H520Z" />
          </svg>
        </button>

        <!-- Right Slided Sidebar containing Contacts & Cognitive Voice Processing -->
        <div class="sidebar ${this.sidebarOpen ? 'open' : ''}">
          <div class="sidebar-header">
            <h2>
              👥 حافظه و بیومتریک صوتی طناز
            </h2>
            <div class="close-btn" @click=${this.toggleSidebar}>
              <svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor">
                <path d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z" />
              </svg>
            </div>
          </div>

          <div class="sidebar-content">
            <!-- Active Biometric Info -->
            <div class="active-speaker-box">
              <div style="font-size: 14px; font-weight: 700; color: #ff453a;">
                🗣️ هم‌صحبت فعال: ${this.activeUser.name}
              </div>
              <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 4px;">
                رابطه: ${this.activeUser.moodState} (دل‌بستگی: ${this.activeUser.loveScore}٪)
              </div>

              <div class="biometrics-grid">
                <div class="bio-metric">
                  <div class="bio-metric-title">فرکانس صدا (PITCH)</div>
                  <div class="bio-metric-val">${this.livePitch > 0 ? html`${this.livePitch} Hz` : '---'}</div>
                </div>
                <div class="bio-metric">
                  <div class="bio-metric-title">طنین صوتی (TIMBRE)</div>
                  <div class="bio-metric-val">${this.liveCentroid > 0 ? html`${this.liveCentroid}` : '---'}</div>
                </div>
              </div>

              <!-- Switches -->
              <div class="switch-container">
                <span class="switch-label">تشخیص اتوماتیک از روی صدا</span>
                <input
                  type="checkbox"
                  class="toggle-switch"
                  ?checked=${this.autoDetectVoice}
                  @change=${(e: any) => this.autoDetectVoice = e.target.checked} />
              </div>

              <button
                class="btn-fingerprint ${this.isTrainingSignature ? 'recording' : ''}"
                @click=${this.triggerTrainSignature}>
                🎙️ ${this.isTrainingSignature ? 'در حال دریافت اثر صدا...' : 'ثبت اثر صدا به کاربر فعلی'}
              </button>
              
              ${this.audioWarning ? html`
                <div style="font-size: 11px; color: #ff9500; margin-top: 10px; line-height: 1.5; text-align: justify;">
                  ⚠️ ${this.audioWarning}
                </div>
              ` : ''}
            </div>

            <div class="section-title">لیست مخاطب‌های طناز (${this.profiles.length})</div>

            <!-- Contacts List loop -->
            ${this.profiles.map(profile => html`
              <div 
                class="profile-card ${this.activeUser.id === profile.id ? 'active' : ''}"
                @click=${() => this.expandedUserId = this.expandedUserId === profile.id ? null : profile.id}>
                
                <div class="profile-meta">
                  <span class="profile-name">
                    👤 ${profile.name}
                    ${profile.voiceSignature ? html`<span style="color: #34c759; font-size: 11px;">(دارای اثر صدا •)</span>` : ''}
                  </span>
                  <span class="profile-mood">${profile.moodState}</span>
                </div>

                <div class="progressbar-container">
                  <div class="progressbar-fill" style="width: ${profile.loveScore}%"></div>
                </div>
                <div style="font-size: 11px; color: rgba(255, 255, 255, 0.5); display: flex; justify-content: space-between;">
                  <span>درجه صمیمیت: ${profile.loveScore}٪</span>
                  <span>خاطرات: ${profile.memories?.length || 0} مورد</span>
                </div>

                <!-- Expanded inner details -->
                ${this.expandedUserId === profile.id ? html`
                  <div class="profile-details" @click=${(e: Event) => e.stopPropagation()}>
                    <div style="font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.7); margin-bottom: 6px;">
                      دفترچه رویدادها و خاطرات:
                    </div>
                    
                    <div class="memories-list">
                      ${profile.memories && profile.memories.length > 0 ? profile.memories.map(memory => html`
                        <div class="memory-row">
                          <span class="memory-tag tag-${memory.category}">${memory.category === 'promise' ? 'قول' : 'خاطره'}</span>
                          ${memory.text}
                        </div>
                      `) : html`
                        <div style="font-size: 11px; color: rgba(255, 255, 255, 0.4); text-align: center; padding: 12px 0;">
                          رویدادی ثبت نشده است. طناز این مخاطب را تازه شناخته!
                        </div>
                      `}
                    </div>

                    <div class="profile-action-row">
                      <button class="btn-small btn-talk" @click=${() => this.selectUserProfile(profile)}>
                        شروع گفتگو با ${profile.name}
                      </button>
                      <button class="btn-small btn-delete" @click=${() => this.handleFormDeleteUser(profile.id)}>
                        حذف مخاطب
                      </button>
                    </div>
                  </div>
                ` : ''}
              </div>
            `)}

            <!-- Manual user creator -->
            <div class="section-title">ثبت دستی مخاطب جدید</div>
            <form class="create-user-form" @submit=${this.handleFormCreateUser}>
              <input
                type="text"
                class="input-field"
                placeholder="نام مخاطب جدید..."
                .value=${this.newUserNameInput}
                @input=${(e: any) => this.newUserNameInput = e.target.value} />
              <button type="submit" class="btn-submit">ثبت کاربر</button>
            </form>
          </div>
        </div>

        <!-- Sphere controls & layout - REMOVED BUTTONS FOR AUTOMATIC CONVERSATION -->
        <!-- Buttons removed: conversation now starts automatically on page load without user interaction -->

        <div id="status"> ${this.error ? html`<span style="color: #ff453a;">${this.error}</span>` : this.status} </div>
        <gdm-live-audio-visuals-3d
          .inputNode=${this.inputNode}
          .outputNode=${this.outputNode}></gdm-live-audio-visuals-3d>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'gdm-live-audio': GdmLiveAudio;
  }
}

// Mount the app into #root
const root = document.querySelector('#root');
if (root && !root.querySelector('gdm-live-audio')) {
  root.appendChild(document.createElement('gdm-live-audio'));
}
