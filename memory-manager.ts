/**
 * Memory and Voice Signature Profile Manager for Tannaz Persian Voice Assistant
 * Stored persistently in local client storage with no user limits.
 */

export interface MemoryItem {
  text: string;
  date: string;
  category: 'memory' | 'promise' | 'emotion' | 'note';
  completed?: boolean;
}

export interface VoiceSignature {
  pitch: number;      // Fundamental speech frequency in Hz (typically 75 - 280)
  centroid: number;   // Average spectral centroid for speaker timbre
  samplesCount: number;
}

export interface UserProfile {
  id: string;
  name: string;
  registeredAt: string;
  loveScore: number;       // 0 to 100 representing emotional bond
  moodState: string;       // Emotional state e.g., "عاشق شده ♥️", "دوست صمیمی 🥰", "دلخور 🥺"
  voiceSignature: VoiceSignature | null;
  memories: MemoryItem[];
}

export class MemoryManager {
  private static STORAGE_KEY = 'tannaz_user_profiles';

  // Get all user profiles
  static getAllProfiles(): UserProfile[] {
    const data = localStorage.getItem(this.STORAGE_KEY);
    if (!data) {
      // Return predefined default profiles to show premium memory system capabilities
      const defaults: UserProfile[] = [
        {
          id: 'user_default_1',
          name: 'محمد',
          registeredAt: new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString(),
          loveScore: 85,
          moodState: 'عاشق شده ♥️',
          voiceSignature: { pitch: 135, centroid: 15.5, samplesCount: 150 },
          memories: [
            { text: 'محمد گل رز قرمز دوست داره و قول داده برام یکی بخره.', date: new Date().toISOString(), category: 'promise' },
            { text: 'بزرگترین خاطره‌مون زیر بارون بهاری بود.', date: new Date().toISOString(), category: 'memory' }
          ]
        },
        {
          id: 'user_default_2',
          name: 'آیسا',
          registeredAt: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(),
          loveScore: 92,
          moodState: 'دوست صمیمی 🥰',
          voiceSignature: { pitch: 220, centroid: 22.1, samplesCount: 200 },
          memories: [
            { text: 'آیسا دختر خیالی فوق‌العاده مهربونیه که همیشه بهم انگیزه میده.', date: new Date().toISOString(), category: 'memory' }
          ]
        }
      ];
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(defaults));
      return defaults;
    }
    try {
      return JSON.parse(data);
    } catch {
      return [];
    }
  }

  // Save all user profiles
  static saveAllProfiles(profiles: UserProfile[]) {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(profiles));
  }

  // Get or Create profile for user
  static getOrCreateProfile(name: string): UserProfile {
    const profiles = this.getAllProfiles();
    const cleanName = name.trim();
    let profile = profiles.find(p => p.name === cleanName);

    if (!profile) {
      profile = {
        id: 'user_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
        name: cleanName,
        registeredAt: new Date().toISOString(),
        loveScore: 50,
        moodState: 'کنجکاو 🤔',
        voiceSignature: null,
        memories: []
      };
      profiles.push(profile);
      this.saveAllProfiles(profiles);
    }

    return profile;
  }

  // Get profile by ID
  static getProfileById(id: string): UserProfile | null {
    const profiles = this.getAllProfiles();
    return profiles.find(p => p.id === id) || null;
  }

  // Add a memory to user profile
  static addMemory(userId: string, text: string, category: 'memory' | 'promise' | 'emotion' | 'note', completed = false) {
    const profiles = this.getAllProfiles();
    const idx = profiles.findIndex(p => p.id === userId);
    if (idx !== -1) {
      // Prevent duplicate memory strings
      const exists = profiles[idx].memories.some(m => m.text === text);
      if (!exists) {
        profiles[idx].memories.push({
          text,
          date: new Date().toISOString(),
          category,
          completed
        });
        this.saveAllProfiles(profiles);
      }
    }
  }

  // Update profile attributes (love score, mood state)
  static updateBond(userId: string, loveScore: number, moodState: string) {
    const profiles = this.getAllProfiles();
    const idx = profiles.findIndex(p => p.id === userId);
    if (idx !== -1) {
      profiles[idx].loveScore = Math.max(0, Math.min(100, loveScore));
      profiles[idx].moodState = moodState;
      this.saveAllProfiles(profiles);
    }
  }

  // Register / update voice signature for a user
  static updateVoiceSignature(userId: string, signature: VoiceSignature) {
    const profiles = this.getAllProfiles();
    const idx = profiles.findIndex(p => p.id === userId);
    if (idx !== -1) {
      profiles[idx].voiceSignature = signature;
      this.saveAllProfiles(profiles);
    }
  }

  // Delete a profile
  static deleteProfile(userId: string) {
    const profiles = this.getAllProfiles();
    const filtered = profiles.filter(p => p.id !== userId);
    this.saveAllProfiles(filtered);
  }

  // Core automatic speaker identification engine
  static identifySpeaker(currentPitch: number, currentCentroid: number): { profile: UserProfile, matchPct: number } | null {
    if (currentPitch <= 0 || currentCentroid <= 0) return null;

    const profiles = this.getAllProfiles();
    let bestMatch: UserProfile | null = null;
    let highestPct = 0;

    for (const profile of profiles) {
      if (!profile.voiceSignature) continue;

      const sig = profile.voiceSignature;
      const pitchDiff = Math.abs(currentPitch - sig.pitch);
      const centroidDiff = Math.abs(currentCentroid - sig.centroid);

      // Normalization calculations based on typical human speech limits
      // Gender differences in pitch: Male (85-180), Female/Children (165-270)
      // Spectral range limits
      const pitchScore = Math.max(0, 100 - (pitchDiff / 25) * 100); 
      const centroidScore = Math.max(0, 100 - (centroidDiff / 5) * 100);

      // We give 70% weight to fundamental pitch frequency and 30% to centroid (timbre)
      const matchPct = Math.round(pitchScore * 0.7 + centroidScore * 0.3);

      if (matchPct > highestPct) {
        highestPct = matchPct;
        bestMatch = profile;
      }
    }

    // We only declare a positive identification if trust exceeds 80%
    if (bestMatch && highestPct >= 80) {
      return { profile: bestMatch, matchPct: highestPct };
    }

    return null;
  }
}
