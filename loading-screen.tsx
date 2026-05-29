// loading-screen.ts - صفحه لودینگ خارق‌العاده با گوی ماه سه‌بعدی
import { useEffect, useRef, useState } from 'react';

interface LoadingScreenProps {
  onComplete: () => void;
}

export default function LoadingScreen({ onComplete }: LoadingScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [progress, setProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) {
      console.error('WebGL not supported');
      onComplete();
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
      
      // ایجاد دهانه‌های ماه
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
        
        // ایجاد جزئیات سطح ماه با FBM و دهانه‌ها
        float detail = fbm(uv * 20.0);
        float craterDetail = craters(uv);
        float surfaceDetail = detail * 0.7 + craterDetail * 0.3;
        
        // رنگ پایه ماه (خاکستری با تنوع)
        vec3 baseColor = vec3(0.6, 0.6, 0.65);
        vec3 darkColor = vec3(0.3, 0.3, 0.35);
        vec3 lightColor = vec3(0.8, 0.8, 0.85);
        
        // ترکیب رنگ‌ها بر اساس جزئیات سطح
        vec3 color = mix(baseColor, darkColor, surfaceDetail);
        color = mix(color, lightColor, surfaceDetail * 0.3);
        
        // نورپردازی PBR
        vec3 lightDir = normalize(u_lightDir);
        float diffuse = max(dot(normal, lightDir), 0.0);
        
        // نور محیطی
        vec3 ambient = vec3(0.1, 0.1, 0.15);
        
        // نور مستقیم
        vec3 directLight = vec3(1.0, 0.95, 0.9) * diffuse * 1.5;
        
        // نور بازتابی از زمین (Earthshine)
        vec3 earthLight = vec3(0.1, 0.15, 0.3) * max(dot(normal, -lightDir), 0.0) * 0.3;
        
        // ترکیب نهایی نور
        vec3 finalColor = color * (ambient + directLight + earthLight);
        
        // اضافه کردن درخشش لبه‌ها (Fresnel effect)
        float fresnel = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 3.0);
        finalColor += vec3(0.2, 0.25, 0.3) * fresnel * 0.5;
        
        // اضافه کردن ذرات معلق (غبار فضایی)
        float particleNoise = fbm(uv * 50.0 + u_time * 0.1);
        finalColor += vec3(0.1, 0.1, 0.15) * particleNoise * 0.2;
        
        // وینیت (تاریک کردن لبه‌ها)
        vec2 centeredUV = uv * 2.0 - 1.0;
        float vignette = 1.0 - length(centeredUV) * 0.5;
        finalColor *= vignette;
        
        // گاما کرنکشن
        finalColor = pow(finalColor, vec3(1.0 / 2.2));
        
        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    // کامپایل shaderها
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
      onComplete();
      return;
    }

    const program = gl.createProgram();
    if (!program) {
      onComplete();
      return;
    }
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      onComplete();
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

    // ایجاد بافرها
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW);

    const texCoordBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, texCoordBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(texCoords), gl.STATIC_DRAW);

    const indexBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);

    // دریافت موقعیت اتریبیوت‌ها و یونیفورم‌ها
    const positionLocation = gl.getAttribLocation(program, 'a_position');
    const texCoordLocation = gl.getAttribLocation(program, 'a_texCoord');
    const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
    const timeLocation = gl.getUniformLocation(program, 'u_time');
    const lightDirLocation = gl.getUniformLocation(program, 'u_lightDir');
    const resolutionLocation = gl.getUniformLocation(program, 'u_resolution');

    // تنظیم ماتریس پروژکشن
    const fieldOfViewRadians = (45 * Math.PI) / 180;
    const aspect = canvas.width / canvas.height;
    const zNear = 0.1;
    const zFar = 100.0;

    const projectionMatrix = createProjectionMatrix(fieldOfViewRadians, aspect, zNear, zFar);
    const cameraMatrix = createLookAtMatrix([0, 0, 3], [0, 0, 0], [0, 1, 0]);
    const viewMatrix = invertMatrix(cameraMatrix);
    const viewProjectionMatrix = multiplyMatrices(projectionMatrix, viewMatrix);

    let startTime = Date.now();
    let animationFrameId: number;

    const render = () => {
      const currentTime = (Date.now() - startTime) / 1000;
      
      // آپدیت پیشرفت لودینگ
      setProgress(prev => {
        const newProgress = prev + 0.5;
        if (newProgress >= 100) {
          setIsLoading(false);
          setTimeout(() => {
            cancelAnimationFrame(animationFrameId);
            onComplete();
          }, 1000);
          return 100;
        }
        return newProgress;
      });

      gl.clearColor(0.0, 0.0, 0.05, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.CULL_FACE);

      // چرخش ماه
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

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
      if (program) {
        gl.deleteProgram(program);
      }
      if (vertexShader) gl.deleteShader(vertexShader);
      if (fragmentShader) gl.deleteShader(fragmentShader);
      if (positionBuffer) gl.deleteBuffer(positionBuffer);
      if (texCoordBuffer) gl.deleteBuffer(texCoordBuffer);
      if (indexBuffer) gl.deleteBuffer(indexBuffer);
    };
  }, [onComplete]);

  // توابع کمکی ریاضی برای ماتریس‌ها
  function createProjectionMatrix(fov: number, aspect: number, near: number, far: number) {
    const f = 1.0 / Math.tan(fov / 2);
    const rangeInv = 1 / (near - far);
    return [
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (near + far) * rangeInv, -1,
      0, 0, near * far * rangeInv * 2, 0
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
      -dotProduct(xAxis, eye), -dotProduct(yAxis, eye), -dotProduct(zAxis, eye), 1
    ];
  }

  function invertMatrix(matrix: number[]) {
    // ساده‌سازی شده برای ماتریس دوربین
    return [
      matrix[0], matrix[4], matrix[8], matrix[12],
      matrix[1], matrix[5], matrix[9], matrix[13],
      matrix[2], matrix[6], matrix[10], matrix[14],
      matrix[3], matrix[7], matrix[11], matrix[15]
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
      0, 0, 0, 1
    ];
  }

  function subtractVectors(a: number[], b: number[]) {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  }

  function crossProduct(a: number[], b: number[]) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ];
  }

  function normalizeVector(v: number[]) {
    const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : [0, 0, 0];
  }

  function dotProduct(a: number[], b: number[]) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black overflow-hidden">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
      
      {/* افکت‌های پس‌زمینه */}
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/20 to-black/80 pointer-events-none" />
      
      {/* نوار پیشرفت */}
      <div className="relative z-10 flex flex-col items-center space-y-6">
        <div className="text-center">
          <h1 className="text-4xl md:text-6xl font-bold text-white mb-2 tracking-wider animate-pulse">
            در حال بارگذاری...
          </h1>
          <p className="text-lg md:text-xl text-gray-300 animate-fade-in">
            آماده‌سازی هوش مصنوعی طناز
          </p>
        </div>
        
        {/* نوار پیشرفت سفارشی */}
        <div className="w-64 md:w-96 h-2 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div 
            className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        
        {/* درصد پیشرفت */}
        <div className="text-2xl font-mono text-cyan-400 animate-bounce">
          {Math.round(progress)}%
        </div>
        
        {/* افکت‌های نوری */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-purple-500/10 rounded-full blur-2xl animate-pulse delay-700" />
      </div>
      
      {/* استایل‌های سفارشی */}
      <style jsx>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 1s ease-out forwards;
        }
        .bg-gradient-radial {
          background: radial-gradient(circle, rgba(0,0,0,0) 0%, rgba(0,0,0,0.4) 50%, rgba(0,0,0,1) 100%);
        }
      `}</style>
    </div>
  );
}
