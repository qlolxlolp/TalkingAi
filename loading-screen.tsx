// loading-screen.ts - صفحه لودینگ خارق‌العاده با گوی ماه سه‌بعدی (Lit)
import {LitElement, css, html} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';

// ----- توابع کمکی ریاضی برای ماتریس‌ها -----
function createProjectionMatrix(fov: number, aspect: number, near: number, far: number) {
  const f = 1.0 / Math.tan(fov / 2);
  const rangeInv = 1 / (near - far);
  return [
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (near + far) * rangeInv, -1,
    0, 0, near * far * rangeInv * 2, 0,
  ];
}

function createLookAtMatrix(eye: number[], target: number[], up: number[]) {
  const zAxis = normalizeVector(subtractVectors(eye, target));
  const xAxis = normalizeVector(crossProduct(up, zAxis));
  const yAxis = crossProduct(zAxis, xAxis);

  return [
    xAxis[0], yAxis[0], zAxis[0], 0,
    xAxis[1], yAxis[1], zAxis[1], 0,
    xAxis[2], yAxis[2], zAxis[2], 0,
    -dotProduct(xAxis, eye), -dotProduct(yAxis, eye), -dotProduct(zAxis, eye), 1,
  ];
}

function invertMatrix(matrix: number[]) {
  // ساده‌سازی شده برای ماتریس دوربین (ترانهاده)
  return [
    matrix[0], matrix[4], matrix[8], matrix[12],
    matrix[1], matrix[5], matrix[9], matrix[13],
    matrix[2], matrix[6], matrix[10], matrix[14],
    matrix[3], matrix[7], matrix[11], matrix[15],
  ];
}

function multiplyMatrices(a: number[], b: number[]) {
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

function createRotationYMatrix(angle: number) {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return [
    c, 0, -s, 0,
    0, 1, 0, 0,
    s, 0, c, 0,
    0, 0, 0, 1,
  ];
}

function subtractVectors(a: number[], b: number[]) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function crossProduct(a: number[], b: number[]) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function normalizeVector(v: number[]) {
  const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
  return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : [0, 0, 0];
}

function dotProduct(a: number[], b: number[]) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

@customElement('loading-screen')
export class LoadingScreen extends LitElement {
  // فراخوانی هنگام پایان لودینگ
  @property({attribute: false}) onComplete: () => void = () => {};

  @state() private progress = 0;

  private animationFrameId = 0;
  private resizeHandler?: () => void;
  private gl?: WebGLRenderingContext | WebGL2RenderingContext | null;
  private program?: WebGLProgram | null;
  private vertexShader?: WebGLShader | null;
  private fragmentShader?: WebGLShader | null;
  private positionBuffer?: WebGLBuffer | null;
  private texCoordBuffer?: WebGLBuffer | null;
  private indexBuffer?: WebGLBuffer | null;
  private finished = false;

  static styles = css`
    :host {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: #000;
      overflow: hidden;
      font-family: system-ui, -apple-system, sans-serif;
    }

    canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    .radial-overlay {
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: radial-gradient(
        circle,
        rgba(0, 0, 0, 0) 0%,
        rgba(0, 0, 0, 0.4) 50%,
        rgba(0, 0, 0, 1) 100%
      );
    }

    .content {
      position: relative;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1.5rem;
    }

    .heading {
      text-align: center;
    }

    .title {
      font-size: 2.5rem;
      font-weight: 700;
      color: #fff;
      margin: 0 0 0.5rem;
      letter-spacing: 0.05em;
      animation: pulse 2s ease-in-out infinite;
    }

    .subtitle {
      font-size: 1.125rem;
      color: #d1d5db;
      margin: 0;
      animation: fade-in 1s ease-out forwards;
    }

    .progress-track {
      width: 16rem;
      height: 0.5rem;
      background: #1f2937;
      border-radius: 9999px;
      overflow: hidden;
      border: 1px solid #374151;
    }

    .progress-fill {
      height: 100%;
      background: linear-gradient(to right, #3b82f6, #8b5cf6, #ec4899);
      transition: width 0.3s ease-out;
    }

    .percent {
      font-size: 1.5rem;
      font-family: ui-monospace, monospace;
      color: #22d3ee;
      animation: bounce 1s infinite;
    }

    .glow-1,
    .glow-2 {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      border-radius: 9999px;
      animation: pulse 2s ease-in-out infinite;
    }

    .glow-1 {
      width: 24rem;
      height: 24rem;
      background: rgba(59, 130, 246, 0.1);
      filter: blur(64px);
    }

    .glow-2 {
      width: 16rem;
      height: 16rem;
      background: rgba(139, 92, 246, 0.1);
      filter: blur(40px);
      animation-delay: 0.7s;
    }

    @media (min-width: 768px) {
      .title {
        font-size: 3.75rem;
      }
      .subtitle {
        font-size: 1.25rem;
      }
      .progress-track {
        width: 24rem;
      }
    }

    @keyframes fade-in {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes pulse {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.5;
      }
    }

    @keyframes bounce {
      0%,
      100% {
        transform: translateY(0);
      }
      50% {
        transform: translateY(-25%);
      }
    }
  `;

  firstUpdated() {
    const canvas = this.renderRoot.querySelector('canvas') as HTMLCanvasElement | null;
    if (!canvas) {
      this.complete();
      return;
    }
    this.initWebGL(canvas);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.cleanup();
  }

  private complete() {
    if (this.finished) return;
    this.finished = true;
    this.onComplete?.();
  }

  private cleanup() {
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler);
    }
    cancelAnimationFrame(this.animationFrameId);
    const gl = this.gl;
    if (gl) {
      if (this.program) gl.deleteProgram(this.program);
      if (this.vertexShader) gl.deleteShader(this.vertexShader);
      if (this.fragmentShader) gl.deleteShader(this.fragmentShader);
      if (this.positionBuffer) gl.deleteBuffer(this.positionBuffer);
      if (this.texCoordBuffer) gl.deleteBuffer(this.texCoordBuffer);
      if (this.indexBuffer) gl.deleteBuffer(this.indexBuffer);
    }
  }

  private initWebGL(canvas: HTMLCanvasElement) {
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as
      | WebGL2RenderingContext
      | WebGLRenderingContext
      | null;
    this.gl = gl;
    if (!gl) {
      console.error('WebGL not supported');
      this.complete();
      return;
    }

    const resizeCanvas = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };
    this.resizeHandler = resizeCanvas;
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

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

      float craters(vec2 uv) {
        float value = 0.0;
        for (int i = 0; i < 12; i++) {
          float fi = float(i);
          vec2 pos = vec2(
            sin(fi * 7.3 + 1.8) * 0.8,
            cos(fi * 9.1 + 4.2) * 0.8
          );
          float size = 0.05 + 0.03 * hash(vec2(fi, fi * 0.5));
          float dist = length(uv - pos);
          float crater = smoothstep(size, size * 0.8, dist);
          crater -= smoothstep(size * 0.8, size * 0.6, dist) * 0.5;
          value += crater * (0.5 + 0.5 * hash(vec2(fi, fi * 0.3)));
        }
        return value;
      }

      void main() {
        vec2 uv = v_texCoord;
        vec3 normal = v_normal;

        float detail = fbm(uv * 20.0);
        float craterDetail = craters(uv);
        float surfaceDetail = detail * 0.7 + craterDetail * 0.3;

        vec3 baseColor = vec3(0.6, 0.6, 0.65);
        vec3 darkColor = vec3(0.3, 0.3, 0.35);
        vec3 lightColor = vec3(0.8, 0.8, 0.85);

        vec3 color = mix(baseColor, darkColor, surfaceDetail);
        color = mix(color, lightColor, surfaceDetail * 0.3);

        vec3 lightDir = normalize(u_lightDir);
        float diffuse = max(dot(normal, lightDir), 0.0);

        vec3 ambient = vec3(0.1, 0.1, 0.15);
        vec3 directLight = vec3(1.0, 0.95, 0.9) * diffuse * 1.5;
        vec3 earthLight = vec3(0.1, 0.15, 0.3) * max(dot(normal, -lightDir), 0.0) * 0.3;

        vec3 finalColor = color * (ambient + directLight + earthLight);

        float fresnel = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 3.0);
        finalColor += vec3(0.2, 0.25, 0.3) * fresnel * 0.5;

        float particleNoise = fbm(uv * 50.0 + u_time * 0.1);
        finalColor += vec3(0.1, 0.1, 0.15) * particleNoise * 0.2;

        vec2 centeredUV = uv * 2.0 - 1.0;
        float vignette = 1.0 - length(centeredUV) * 0.5;
        finalColor *= vignette;

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
    this.vertexShader = vertexShader;
    this.fragmentShader = fragmentShader;

    if (!vertexShader || !fragmentShader) {
      this.complete();
      return;
    }

    const program = gl.createProgram();
    this.program = program;
    if (!program) {
      this.complete();
      return;
    }
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      this.complete();
      return;
    }

    gl.useProgram(program);

    // ایجاد هندسه کره
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
    this.positionBuffer = positionBuffer;
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW);

    const texCoordBuffer = gl.createBuffer();
    this.texCoordBuffer = texCoordBuffer;
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(texCoords), gl.STATIC_DRAW);

    const indexBuffer = gl.createBuffer();
    this.indexBuffer = indexBuffer;
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);

    const positionLocation = gl.getAttribLocation(program, 'a_position');
    const texCoordLocation = gl.getAttribLocation(program, 'a_texCoord');
    const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
    const timeLocation = gl.getUniformLocation(program, 'u_time');
    const lightDirLocation = gl.getUniformLocation(program, 'u_lightDir');
    const resolutionLocation = gl.getUniformLocation(program, 'u_resolution');

    const fieldOfViewRadians = (45 * Math.PI) / 180;
    const aspect = canvas.width / canvas.height;
    const zNear = 0.1;
    const zFar = 100.0;

    const projectionMatrix = createProjectionMatrix(fieldOfViewRadians, aspect, zNear, zFar);
    const cameraMatrix = createLookAtMatrix([0, 0, 3], [0, 0, 0], [0, 1, 0]);
    const viewMatrix = invertMatrix(cameraMatrix);
    const viewProjectionMatrix = multiplyMatrices(projectionMatrix, viewMatrix);

    const startTime = Date.now();

    const render = () => {
      const currentTime = (Date.now() - startTime) / 1000;

      // آپدیت پیشرفت لودینگ
      const newProgress = this.progress + 0.5;
      if (newProgress >= 100) {
        this.progress = 100;
        setTimeout(() => {
          cancelAnimationFrame(this.animationFrameId);
          this.complete();
        }, 1000);
      } else {
        this.progress = newProgress;
      }

      gl.clearColor(0.0, 0.0, 0.05, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.CULL_FACE);

      const rotationMatrix = createRotationYMatrix(currentTime * 0.1);
      const modelViewMatrix = multiplyMatrices(viewProjectionMatrix, rotationMatrix);

      gl.uniformMatrix4fv(matrixLocation, false, modelViewMatrix);
      gl.uniform1f(timeLocation, currentTime);
      gl.uniform3f(lightDirLocation, 1.0, 0.5, 1.0);
      gl.uniform2f(resolutionLocation, canvas.width, canvas.height);

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

  render() {
    return html`
      <canvas></canvas>
      <div class="radial-overlay"></div>

      <div class="content">
        <div class="heading">
          <h1 class="title">در حال بارگذاری...</h1>
          <p class="subtitle">آماده‌سازی هوش مصنوعی طناز</p>
        </div>

        <div class="progress-track">
          <div class="progress-fill" style="width: ${this.progress}%"></div>
        </div>

        <div class="percent">${Math.round(this.progress)}%</div>

        <div class="glow-1"></div>
        <div class="glow-2"></div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'loading-screen': LoadingScreen;
  }
}
