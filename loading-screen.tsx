// loading-screen.ts - صفحه لودینگ خارق‌العاده با گوی ماه سه‌بعدی
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('loading-screen-component')
export default class LoadingScreen extends LitElement {
  @property({ type: Boolean }) complete = false;
  
  private canvasRef: HTMLCanvasElement | null = null;
  private progress: number = 0;
  private isLoading: boolean = true;
  private animationFrameId: number = 0;
  private startTime: number = 0;
  
  static styles = css`
    :host {
      display: block;
      width: 100%;
      height: 100vh;
      background: radial-gradient(ellipse at center, #1a0b14 0%, #0a0508 100%);
      position: fixed;
      top: 0;
      left: 0;
      z-index: 9999;
    }
    
    .loading-container {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
    }
    
    canvas {
      max-width: 100%;
      max-height: 60vh;
    }
    
    .progress-container {
      position: absolute;
      bottom: 15%;
      width: 300px;
      max-width: 80vw;
      text-align: center;
    }
    
    .progress-bar {
      width: 100%;
      height: 4px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 2px;
      overflow: hidden;
      margin-bottom: 12px;
    }
    
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #ff453a, #ff9500, #ffd60a, #34c759, #007aff, #bf5af2);
      background-size: 300% 100%;
      animation: rainbow 2s linear infinite;
      transition: width 0.3s ease;
    }
    
    @keyframes rainbow {
      0% { background-position: 0% 50%; }
      100% { background-position: 300% 50%; }
    }
    
    .loading-text {
      font-family: 'Vazirmatn', 'Tahoma', sans-serif;
      color: rgba(255, 255, 255, 0.8);
      font-size: 14px;
      letter-spacing: 1px;
    }
    
    .percentage {
      font-family: 'JetBrains Mono', monospace;
      font-size: 24px;
      color: #00bcd4;
      margin-top: 8px;
      animation: pulse 1s ease-in-out infinite;
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
  `;

  firstUpdated() {
    this.canvasRef = this.shadowRoot!.querySelector('#moon-canvas');
    if (this.canvasRef) {
      this.initWebGL();
    }
    this.startTime = performance.now();
    this.runAnimation();
  }

  private initWebGL() {
    const canvas = this.canvasRef;
    if (!canvas) return;

    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) {
      console.error('WebGL not supported');
      this.completeLoading();
      return;
    }

    // تنظیم اندازه کانواس
    const resizeCanvas = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Shaderهای ماه با جزئیات میکروسکوپی
    const vertexShaderSource = `
      attribute vec4 a_position;
      attribute vec2 a_texCoord;
      uniform mat4 u_matrix;
      varying vec2 v_texCoord;
      varying vec3 v_normal;
      varying vec3 v_position;
      
      void main() {
        gl_Position = u_matrix * a_position;
        v_texCoord = a_texCoord;
        v_normal = normalize((u_matrix * vec4(a_position.xyz, 0.0)).xyz);
        v_position = (u_matrix * a_position).xyz;
      }
    `;

    const fragmentShaderSource = `
      precision highp float;
      varying vec2 v_texCoord;
      varying vec3 v_normal;
      varying vec3 v_position;
      
      uniform float u_time;
      uniform vec3 u_lightDir;
      uniform vec2 u_resolution;
      
      // تابع نویز برای ایجاد جزئیات سطح ماه
      float hash(vec2 p) {
        p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
        return -1.0 + 2.0 * fract(sin(p.x + p.y * 43758.5453123) * 43758.5453123);
      }
      
      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));
        return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
      }
      
      float fbm(vec2 p) {
        float value = 0.0;
        float amplitude = 0.5;
        for (int i = 0; i < 6; i++) {
          value += amplitude * noise(p);
          p *= 2.0;
          amplitude *= 0.5;
        }
        return value;
      }
      
      void main() {
        vec2 uv = v_texCoord;
        
        // ایجاد سطح ناهموار ماه با استفاده از FBM
        float displacement = fbm(uv * 10.0 + u_time * 0.05);
        vec3 normal = normalize(v_normal + vec3(displacement * 0.1, displacement * 0.1, 1.0));
        
        // نورپردازی PBR ساده
        vec3 lightDir = normalize(u_lightDir);
        float diffuse = max(dot(normal, lightDir), 0.0);
        
        // رنگ خاکستری ماه با تنوع
        vec3 moonColor = vec3(0.8, 0.8, 0.85);
        vec3 ambient = vec3(0.1, 0.1, 0.15);
        
        // سایه‌زنی حجمی
        float shadow = smoothstep(0.0, 0.3, displacement);
        vec3 finalColor = moonColor * (diffuse + ambient) * (1.0 - shadow * 0.5);
        
        // اضافه کردن درخشش لبه‌ای
        float fresnel = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 3.0);
        finalColor += vec3(0.3, 0.4, 0.5) * fresnel * 0.3;
        
        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    // کامپایل shaderها
    const createShader = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) throw new Error('Unable to create shader');
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compile error:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        throw new Error('Shader compilation failed');
      }
      return shader;
    };

    const vertexShader = createShader(gl.VERTEX_SHADER, vertexShaderSource);
    const fragmentShader = createShader(gl.FRAGMENT_SHADER, fragmentShaderSource);

    const program = gl.createProgram();
    if (!program) throw new Error('Unable to create program');
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      throw new Error('Program linking failed');
    }
    gl.useProgram(program);

    // ایجاد هندسه کره
    const sphereData = this.createSphere(1.0, 64, 64);
    
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(sphereData.positions), gl.STATIC_DRAW);
    
    const texCoordBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(sphereData.texCoords), gl.STATIC_DRAW);
    
    const indexBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(sphereData.indices), gl.STATIC_DRAW);

    const positionLocation = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(positionLocation);
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);

    const texCoordLocation = gl.getAttribLocation(program, 'a_texCoord');
    gl.enableVertexAttribArray(texCoordLocation);
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.vertexAttribPointer(texCoordLocation, 2, gl.FLOAT, false, 0, 0);

    const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
    const timeLocation = gl.getUniformLocation(program, 'u_time');
    const lightDirLocation = gl.getUniformLocation(program, 'u_lightDir');

    // ماتریس‌های تبدیل
    const m4 = {
      perspective: (fov: number, aspect: number, near: number, far: number) => {
        const f = 1.0 / Math.tan(fov / 2);
        const nf = 1 / (near - far);
        return [
          f / aspect, 0, 0, 0,
          0, f, 0, 0,
          0, 0, (far + near) * nf, -1,
          0, 0, (2 * far * near) * nf, 0
        ];
      },
      translate: (x: number, y: number, z: number) => {
        return [
          1, 0, 0, 0,
          0, 1, 0, 0,
          0, 0, 1, 0,
          x, y, z, 1
        ];
      },
      rotateY: (angle: number) => {
        const c = Math.cos(angle);
        const s = Math.sin(angle);
        return [
          c, 0, -s, 0,
          0, 1, 0, 0,
          s, 0, c, 0,
          0, 0, 0, 1
        ];
      },
      multiply: (a: number[], b: number[]) => {
        const result = new Array(16).fill(0);
        for (let i = 0; i < 4; i++) {
          for (let j = 0; j < 4; j++) {
            for (let k = 0; k < 4; k++) {
              result[i * 4 + j] += a[i * 4 + k] * b[k * 4 + j];
            }
          }
        }
        return result;
      }
    };

    let rotation = 0;
    const render = (time: number) => {
      time *= 0.001;
      rotation += 0.005;

      gl.clearColor(0.0, 0.0, 0.0, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.CULL_FACE);

      const aspect = canvas.clientWidth / canvas.clientHeight;
      const projectionMatrix = m4.perspective(Math.PI / 4, aspect, 0.1, 100.0);
      const translationMatrix = m4.translate(0, 0, -3);
      const rotationMatrix = m4.rotateY(rotation);
      
      let matrix = m4.multiply(projectionMatrix, translationMatrix);
      matrix = m4.multiply(matrix, rotationMatrix);

      gl.uniformMatrix4fv(matrixLocation, false, new Float32Array(matrix));
      gl.uniform1f(timeLocation, time);
      gl.uniform3f(lightDirLocation, 1.0, 0.5, 1.0);

      gl.drawElements(gl.TRIANGLES, sphereData.indices.length, gl.UNSIGNED_SHORT, 0);

      this.animationFrameId = requestAnimationFrame(render);
    };

    render(0);
  }

  private createSphere(radius: number, widthSegments: number, heightSegments: number) {
    const positions: number[] = [];
    const texCoords: number[] = [];
    const indices: number[] = [];

    for (let y = 0; y <= heightSegments; y++) {
      for (let x = 0; x <= widthSegments; x++) {
        const u = x / widthSegments;
        const v = y / heightSegments;
        const theta = u * Math.PI * 2;
        const phi = v * Math.PI;

        const px = radius * Math.sin(phi) * Math.cos(theta);
        const py = radius * Math.cos(phi);
        const pz = radius * Math.sin(phi) * Math.sin(theta);

        positions.push(px, py, pz);
        texCoords.push(u, v);
      }
    }

    for (let y = 0; y < heightSegments; y++) {
      for (let x = 0; x < widthSegments; x++) {
        const a = y * (widthSegments + 1) + x;
        const b = a + 1;
        const c = (y + 1) * (widthSegments + 1) + x;
        const d = c + 1;

        if (y !== 0) {
          indices.push(a, c, b);
        }
        if (y !== heightSegments - 1) {
          indices.push(b, c, d);
        }
      }
    }

    return { positions, texCoords, indices };
  }

  private runAnimation() {
    const elapsed = performance.now() - this.startTime;
    const duration = 3000; // 3 seconds loading
    
    this.progress = Math.min(elapsed / duration, 1) * 100;
    
    if (this.progress < 100) {
      this.animationFrameId = requestAnimationFrame(() => this.runAnimation());
    } else {
      setTimeout(() => this.completeLoading(), 500);
    }
    
    this.requestUpdate();
  }

  private completeLoading() {
    this.dispatchEvent(new CustomEvent('loading-complete', { bubbles: true, composed: true }));
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
  }

  render() {
    return html`
      <div class="loading-container">
        <canvas id="moon-canvas"></canvas>
        <div class="progress-container">
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${this.progress}%"></div>
          </div>
          <div class="loading-text">در حال بارگذاری هوش مصنوعی طناز...</div>
          <div class="percentage">${Math.round(this.progress)}%</div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'loading-screen-component': LoadingScreen;
  }
}
