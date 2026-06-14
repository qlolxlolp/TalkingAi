// loading-screen.ts - صفحه لودینگ خارق‌العاده با گوی ماه سه‌بعدی
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';

@customElement('loading-screen')
export class LoadingScreen extends LitElement {
  @state() progress = 0;
  @state() isLoading = true;
  private canvas: HTMLCanvasElement | null = null;
  private animationFrameId: number | null = null;
  private startTime = 0;

  static styles = css`
    :host {
      display: block;
      width: 100vw;
      height: 100vh;
      position: fixed;
      top: 0;
      left: 0;
      z-index: 50;
    }
    
    .loading-container {
      position: fixed;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: #000;
      overflow: hidden;
    }
    
    canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }
    
    .backdrop {
      position: absolute;
      inset: 0;
      background: radial-gradient(circle, rgba(0,0,0,0) 0%, rgba(0,0,0,0.4) 50%, rgba(0,0,0,1) 100%);
      pointer-events: none;
    }
    
    .content {
      position: relative;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1.5rem;
      text-align: center;
    }
    
    h1 {
      font-size: clamp(2rem, 8vw, 3.5rem);
      font-weight: bold;
      color: white;
      margin: 0;
      letter-spacing: 0.15em;
      animation: pulse 2s ease-in-out infinite;
    }
    
    p {
      font-size: clamp(1rem, 3vw, 1.25rem);
      color: #d1d5db;
      margin: 0;
      animation: fadeIn 1s ease-out forwards;
    }
    
    .progress-bar-container {
      width: 16rem;
      height: 0.5rem;
      background: #1f2937;
      border-radius: 9999px;
      border: 1px solid #374151;
      overflow: hidden;
    }
    
    .progress-bar {
      height: 100%;
      background: linear-gradient(to right, #3b82f6, #a855f7, #ec4899);
      transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .progress-text {
      font-size: 1.5rem;
      font-family: monospace;
      color: #06b6d4;
      animation: bounce 1s ease-in-out infinite;
    }
    
    .glow-bg {
      position: absolute;
      border-radius: 50%;
      opacity: 0.1;
      animation: pulse 3s ease-in-out infinite;
    }
    
    .glow-1 {
      width: 24rem;
      height: 24rem;
      background: #3b82f6;
      filter: blur(3rem);
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }
    
    .glow-2 {
      width: 16rem;
      height: 16rem;
      background: #a855f7;
      filter: blur(2rem);
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      animation: pulse 3s ease-in-out infinite 700ms;
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.8; }
    }
    
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-5px); }
    }
  `;

  render() {
    return html`
      <div class="loading-container">
        <canvas></canvas>
        <div class="backdrop"></div>
        
        <div class="content">
          <div>
            <h1>در حال بارگذاری...</h1>
            <p>آماده‌سازی هوش مصنوعی طناز</p>
          </div>
          
          <div class="progress-bar-container">
            <div class="progress-bar" style="width: ${this.progress}%"></div>
          </div>
          
          <div class="progress-text">${Math.round(this.progress)}%</div>
        </div>
        
        <div class="glow-bg glow-1"></div>
        <div class="glow-bg glow-2"></div>
      </div>
    `;
  }

  firstUpdated() {
    this.canvas = this.shadowRoot?.querySelector('canvas') || null;
    if (this.canvas) {
      this.initWebGL();
      this.startProgressAnimation();
    }
  }

  private initWebGL() {
    if (!this.canvas) return;

    const gl = this.canvas.getContext('webgl2') || this.canvas.getContext('webgl');
    if (!gl) {
      console.error('WebGL not supported');
      this.completeLoading();
      return;
    }

    const resizeCanvas = () => {
      if (!this.canvas) return;
      this.canvas.width = window.innerWidth * window.devicePixelRatio;
      this.canvas.height = window.innerHeight * window.devicePixelRatio;
      gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const vertexShaderSource = `
      attribute vec4 a_position;
      attribute vec2 a_texCoord;
      uniform mat4 u_matrix;
      varying vec2 v_texCoord;
      varying vec3 v_normal;
      
      void main() {
        gl_Position = u_matrix * a_position;
        v_texCoord = a_texCoord;
        v_normal = normalize((u_matrix * vec4(a_position.xyz, 0.0)).xyz);
      }
    `;

    const fragmentShaderSource = `
      precision highp float;
      varying vec2 v_texCoord;
      varying vec3 v_normal;
      uniform float u_time;
      
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
        vec3 normal = v_normal;
        
        float detail = fbm(uv * 20.0);
        vec3 baseColor = vec3(0.6, 0.6, 0.65);
        vec3 darkColor = vec3(0.3, 0.3, 0.35);
        vec3 color = mix(baseColor, darkColor, detail);
        
        vec3 lightDir = normalize(vec3(1.0, 0.5, 1.0));
        float diffuse = max(dot(normal, lightDir), 0.0);
        vec3 ambient = vec3(0.1, 0.1, 0.15);
        
        vec3 finalColor = color * (ambient + diffuse * 1.5);
        finalColor = pow(finalColor, vec3(1.0 / 2.2));
        
        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    const createShader = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compile error:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    };

    const vertexShader = createShader(gl.VERTEX_SHADER, vertexShaderSource);
    const fragmentShader = createShader(gl.FRAGMENT_SHADER, fragmentShaderSource);

    if (!vertexShader || !fragmentShader) {
      this.completeLoading();
      return;
    }

    const program = gl.createProgram();
    if (!program) {
      this.completeLoading();
      return;
    }

    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      this.completeLoading();
      return;
    }

    gl.useProgram(program);

    // Create sphere geometry
    const sphereRadius = 1.0;
    const latitudeBands = 64;
    const longitudeBands = 64;
    const positions: number[] = [];
    const texCoords: number[] = [];
    const indices: number[] = [];

    for (let lat = 0; lat <= latitudeBands; lat++) {
      const theta = (lat * Math.PI) / latitudeBands;
      const sinTheta = Math.sin(theta);
      const cosTheta = Math.cos(theta);

      for (let lon = 0; lon <= longitudeBands; lon++) {
        const phi = (lon * 2 * Math.PI) / longitudeBands;
        const sinPhi = Math.sin(phi);
        const cosPhi = Math.cos(phi);

        const x = cosPhi * sinTheta;
        const y = cosTheta;
        const z = sinPhi * sinTheta;

        positions.push(sphereRadius * x, sphereRadius * y, sphereRadius * z);
        texCoords.push(lon / longitudeBands, lat / latitudeBands);
      }
    }

    for (let lat = 0; lat < latitudeBands; lat++) {
      for (let lon = 0; lon < longitudeBands; lon++) {
        const first = lat * (longitudeBands + 1) + lon;
        const second = first + longitudeBands + 1;
        indices.push(first, second, first + 1);
        indices.push(second, second + 1, first + 1);
      }
    }

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW);

    const texCoordBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(texCoords), gl.STATIC_DRAW);

    const indexBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);

    const positionLocation = gl.getAttribLocation(program, 'a_position');
    const texCoordLocation = gl.getAttribLocation(program, 'a_texCoord');
    const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
    const timeLocation = gl.getUniformLocation(program, 'u_time');

    const projectionMatrix = this.createProjectionMatrix(
      (45 * Math.PI) / 180,
      this.canvas.width / this.canvas.height,
      0.1,
      100.0
    );

    const cameraMatrix = this.createLookAtMatrix([0, 0, 3], [0, 0, 0], [0, 1, 0]);
    const viewMatrix = this.invertMatrix(cameraMatrix);
    const viewProjectionMatrix = this.multiplyMatrices(projectionMatrix, viewMatrix);

    this.startTime = Date.now();

    const render = () => {
      const currentTime = (Date.now() - this.startTime) / 1000;

      gl.clearColor(0.0, 0.0, 0.05, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.CULL_FACE);

      const rotationMatrix = this.createRotationYMatrix(currentTime * 0.1);
      const modelViewMatrix = this.multiplyMatrices(viewProjectionMatrix, rotationMatrix);

      gl.uniformMatrix4fv(matrixLocation, false, modelViewMatrix);
      gl.uniform1f(timeLocation, currentTime);

      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
      gl.enableVertexAttribArray(texCoordLocation);
      gl.vertexAttribPointer(texCoordLocation, 2, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
      gl.drawElements(gl.TRIANGLES, indices.length, gl.UNSIGNED_SHORT, 0);

      this.animationFrameId = requestAnimationFrame(render);
    };

    render();
  }

  private startProgressAnimation() {
    const interval = setInterval(() => {
      if (this.progress < 100) {
        this.progress += Math.random() * 30;
        if (this.progress > 100) this.progress = 100;
      }
    }, 500);

    const cleanup = () => {
      clearInterval(interval);
    };

    window.addEventListener('load', cleanup);
  }

  private completeLoading() {
    this.isLoading = false;
    this.progress = 100;
    setTimeout(() => {
      this.dispatchEvent(new CustomEvent('loading-complete'));
    }, 500);
  }

  private createProjectionMatrix(fov: number, aspect: number, near: number, far: number) {
    const f = 1.0 / Math.tan(fov / 2);
    const rangeInv = 1 / (near - far);
    return [
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (near + far) * rangeInv, -1,
      0, 0, near * far * rangeInv * 2, 0
    ];
  }

  private createLookAtMatrix(eye: number[], target: number[], up: number[]) {
    const zAxis = this.normalizeVector(this.subtractVectors(eye, target));
    const xAxis = this.normalizeVector(this.crossProduct(up, zAxis));
    const yAxis = this.crossProduct(zAxis, xAxis);

    return [
      xAxis[0], yAxis[0], zAxis[0], 0,
      xAxis[1], yAxis[1], zAxis[1], 0,
      xAxis[2], yAxis[2], zAxis[2], 0,
      -this.dotProduct(xAxis, eye), -this.dotProduct(yAxis, eye), -this.dotProduct(zAxis, eye), 1
    ];
  }

  private invertMatrix(matrix: number[]) {
    return [
      matrix[0], matrix[4], matrix[8], matrix[12],
      matrix[1], matrix[5], matrix[9], matrix[13],
      matrix[2], matrix[6], matrix[10], matrix[14],
      matrix[3], matrix[7], matrix[11], matrix[15]
    ];
  }

  private multiplyMatrices(a: number[], b: number[]) {
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

  private createRotationYMatrix(angle: number) {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    return [
      c, 0, -s, 0,
      0, 1, 0, 0,
      s, 0, c, 0,
      0, 0, 0, 1
    ];
  }

  private subtractVectors(a: number[], b: number[]) {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  }

  private crossProduct(a: number[], b: number[]) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ];
  }

  private normalizeVector(v: number[]) {
    const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : [0, 0, 0];
  }

  private dotProduct(a: number[], b: number[]) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'loading-screen': LoadingScreen;
  }
}
