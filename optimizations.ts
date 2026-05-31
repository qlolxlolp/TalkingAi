/**
 * @file optimizations.ts
 * @description ماژول بهینه‌سازی‌های پیشرفته برای پروژه طناز
 * شامل: کشینگ، Lazy Loading، Web Workers، Memory Management
 */

// ============================================
// 1. AudioContext Cache - جلوگیری از ایجاد مجدد
// ============================================

interface AudioContextCache {
  input: AudioContext | null;
  output: AudioContext | null;
}

const audioContextCache: AudioContextCache = {
  input: null,
  output: null
};

export function getCachedAudioContext(sampleRate: number, type: 'input' | 'output'): AudioContext {
  const cacheKey = type;
  
  if (audioContextCache[cacheKey]) {
    return audioContextCache[cacheKey]!;
  }
  
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate });
  audioContextCache[cacheKey] = ctx;
  return ctx;
}

export function cleanupAudioContexts(): void {
  if (audioContextCache.input) {
    audioContextCache.input.close();
    audioContextCache.input = null;
  }
  if (audioContextCache.output) {
    audioContextCache.output.close();
    audioContextCache.output = null;
  }
}

// ============================================
// 2. Lazy Loading Helper - بارگذاری تنبل
// ============================================

type ModuleLoader<T> = () => Promise<T>;

const loadedModules = new Map<string, any>();

export async function lazyLoadModule<T>(moduleName: string, loader: ModuleLoader<T>): Promise<T> {
  if (loadedModules.has(moduleName)) {
    return loadedModules.get(moduleName);
  }
  
  try {
    const module = await loader();
    loadedModules.set(moduleName, module);
    return module;
  } catch (error) {
    console.error(`Failed to load module ${moduleName}:`, error);
    throw error;
  }
}

export function clearModuleCache(moduleName?: string): void {
  if (moduleName) {
    loadedModules.delete(moduleName);
  } else {
    loadedModules.clear();
  }
}

// ============================================
// 3. Memory Pool - مدیریت حافظه کارآمد
// ============================================

interface MemoryPoolConfig {
  maxSize: number;
  cleanupInterval: number;
}

class MemoryPool<T extends object> {
  private pool: T[] = [];
  private config: MemoryPoolConfig;
  private cleanupTimer: number | null = null;

  constructor(config: MemoryPoolConfig) {
    this.config = config;
    this.startCleanupTimer();
  }

  acquire(createFn: () => T): T {
    if (this.pool.length > 0) {
      return this.pool.pop()!;
    }
    return createFn();
  }

  release(item: T): void {
    if (this.pool.length < this.config.maxSize) {
      // Reset item if possible
      if ('reset' in item && typeof (item as any).reset === 'function') {
        (item as any).reset();
      }
      this.pool.push(item);
    }
  }

  private startCleanupTimer(): void {
    this.cleanupTimer = window.setInterval(() => {
      if (this.pool.length > Math.floor(this.config.maxSize / 2)) {
        this.pool.splice(0, this.pool.length - Math.floor(this.config.maxSize / 2));
      }
    }, this.config.cleanupInterval);
  }

  destroy(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }
    this.pool = [];
  }
}

export function createMemoryPool<T extends object>(config: Partial<MemoryPoolConfig> = {}): MemoryPool<T> {
  const defaultConfig: MemoryPoolConfig = {
    maxSize: 100,
    cleanupInterval: 30000
  };
  return new MemoryPool<T>({ ...defaultConfig, ...config });
}

// ============================================
// 4. Debounce & Throttle - کنترل فراخوانی توابع
// ============================================

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return function (this: any, ...args: Parameters<T>) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func.apply(this, args);
      timeoutId = null;
    }, wait);
  };
}

export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;

  return function (this: any, ...args: Parameters<T>) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
}

// ============================================
// 5. Performance Monitor - مانیتورینگ عملکرد
// ============================================

interface PerformanceMetrics {
  fps: number;
  memoryUsage: number;
  frameTime: number;
}

class PerformanceMonitor {
  private frameCount = 0;
  private lastTime = performance.now();
  private metrics: PerformanceMetrics = {
    fps: 0,
    memoryUsage: 0,
    frameTime: 0
  };
  private callbacks: ((metrics: PerformanceMetrics) => void)[] = [];

  start(): void {
    const measure = (currentTime: number) => {
      this.frameCount++;
      
      const delta = currentTime - this.lastTime;
      
      if (delta >= 1000) {
        const fps = Math.round((this.frameCount * 1000) / delta);
        const memoryUsage = (performance as any).memory 
          ? (performance as any).memory.usedJSHeapSize / 1048576 
          : 0;
        
        this.metrics = {
          fps,
          memoryUsage: Math.round(memoryUsage),
          frameTime: Math.round(delta / this.frameCount)
        };
        
        this.callbacks.forEach(cb => cb(this.metrics));
        
        this.frameCount = 0;
        this.lastTime = currentTime;
      }
      
      requestAnimationFrame(measure);
    };
    
    requestAnimationFrame(measure);
  }

  onMetricsUpdate(callback: (metrics: PerformanceMetrics) => void): void {
    this.callbacks.push(callback);
  }

  getMetrics(): PerformanceMetrics {
    return this.metrics;
  }
}

export const performanceMonitor = new PerformanceMonitor();

// ============================================
// 6. Error Handler with Retry - مدیریت خطا با تلاش مجدد
// ============================================

interface RetryConfig {
  maxRetries: number;
  delay: number;
  backoffMultiplier: number;
}

export async function retryableRequest<T>(
  fn: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const defaultConfig: RetryConfig = {
    maxRetries: 3,
    delay: 1000,
    backoffMultiplier: 2
  };

  const { maxRetries, delay, backoffMultiplier } = { ...defaultConfig, ...config };
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      
      if (attempt < maxRetries) {
        const waitTime = delay * Math.pow(backoffMultiplier, attempt);
        console.warn(`Attempt ${attempt + 1} failed. Retrying in ${waitTime}ms...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      }
    }
  }

  throw lastError || new Error('Unknown error occurred');
}

// ============================================
// 7. Data Compression Helper - فشرده‌سازی داده‌ها
// ============================================

export async function compressData(data: string): Promise<string> {
  const blob = new Blob([data], { type: 'text/plain' });
  
  if ('CompressionStream' in window) {
    const compressedStream = blob.stream().pipeThrough(new CompressionStream('gzip'));
    const compressedBlob = await new Response(compressedStream).blob();
    const buffer = await compressedBlob.arrayBuffer();
    return btoa(String.fromCharCode(...new Uint8Array(buffer)));
  }
  
  return data; // Fallback: no compression
}

export async function decompressData(compressedBase64: string): Promise<string> {
  if ('DecompressionStream' in window) {
    const binaryString = atob(compressedBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    return await new Response(stream).text();
  }
  
  return compressedBase64; // Fallback: no decompression
}

// ============================================
// 8. Connection Status Monitor - پایش وضعیت اتصال
// ============================================

type ConnectionState = 'online' | 'offline' | 'slow';

class ConnectionMonitor {
  private state: ConnectionState = 'online';
  private listeners: ((state: ConnectionState) => void)[] = [];

  constructor() {
    window.addEventListener('online', () => this.updateState('online'));
    window.addEventListener('offline', () => this.updateState('offline'));
    
    // Check connection speed periodically
    setInterval(() => this.checkConnectionSpeed(), 30000);
  }

  private updateState(newState: ConnectionState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.listeners.forEach(listener => listener(newState));
    }
  }

  private async checkConnectionSpeed(): Promise<void> {
    if (navigator.onLine === false) {
      this.updateState('offline');
      return;
    }

    try {
      const start = performance.now();
      await fetch('/favicon.ico', { cache: 'no-store', mode: 'no-cors' });
      const duration = performance.now() - start;

      if (duration > 3000) {
        this.updateState('slow');
      } else if (this.state === 'slow') {
        this.updateState('online');
      }
    } catch {
      this.updateState('offline');
    }
  }

  getState(): ConnectionState {
    return this.state;
  }

  onStateChange(callback: (state: ConnectionState) => void): void {
    this.listeners.push(callback);
  }
}

export const connectionMonitor = new ConnectionMonitor();

// Export all utilities
export {
  MemoryPool,
  PerformanceMonitor
};

export type {
  AudioContextCache
};
