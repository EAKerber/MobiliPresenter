window.MOBILI_I1_ASSETS = Object.freeze({
  projectImage: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#75828b"/>
          <stop offset="1" stop-color="#b9b7a9"/>
        </linearGradient>
      </defs>
      <rect width="800" height="500" fill="url(#sky)"/>
      <path d="M0 370 L160 310 L300 350 L470 270 L800 340 L800 500 L0 500 Z" fill="#51634f"/>
      <g fill="#4a4846" stroke="#c2beb4" stroke-width="5">
        <rect x="105" y="150" width="120" height="245" rx="4"/>
        <rect x="245" y="105" width="135" height="290" rx="4"/>
        <rect x="405" y="165" width="115" height="230" rx="4"/>
        <rect x="545" y="125" width="145" height="270" rx="4"/>
      </g>
      <g fill="#d8d2c6" opacity=".55">
        <path d="M125 180h80v8h-80zm0 36h80v8h-80zm0 36h80v8h-80zm0 36h80v8h-80z"/>
        <path d="M270 140h85v8h-85zm0 38h85v8h-85zm0 38h85v8h-85zm0 38h85v8h-85z"/>
        <path d="M565 160h105v8H565zm0 40h105v8H565zm0 40h105v8H565zm0 40h105v8H565z"/>
      </g>
      <circle cx="400" cy="220" r="72" fill="none" stroke="#fff" stroke-width="8" opacity=".92"/>
      <path d="M350 250c35-85 85-92 105-55-48 3-82 28-105 55zm12 8c55-35 88-23 102 4-45-5-72 5-102 34z" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round"/>
      <text x="400" y="335" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="38" letter-spacing="5">RNI RESERVA</text>
      <text x="400" y="380" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="34" letter-spacing="3">CACHOEIRINHA</text>
    </svg>
  `)}`,
  referenceComposition: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1423 810">
      <rect width="1423" height="810" fill="#e7e2d9"/>
      <g stroke="#c9c3b8" stroke-width="2" opacity=".7">
        ${Array.from({length: 15}, (_, i) => `<path d="M${i * 102} 0v810"/>`).join("")}
        ${Array.from({length: 9}, (_, i) => `<path d="M0 ${i * 102}h1423"/>`).join("")}
      </g>
      <rect x="82" y="480" width="205" height="260" rx="20" fill="#a7aaa9"/>
      <circle cx="184" cy="608" r="72" fill="#777b7c" stroke="#d9d9d6" stroke-width="16"/>
      <rect x="330" y="535" width="110" height="205" fill="#eeeae2"/>
      <rect x="500" y="500" width="195" height="245" fill="#9d9c98"/>
      <rect x="1060" y="145" width="210" height="600" rx="10" fill="#a4a5a2"/>
      <path d="M440 495h620" stroke="#b39c7c" stroke-width="24"/>
      <path d="M440 505h620" stroke="#ddd5c9" stroke-width="10"/>
      <text x="711" y="770" text-anchor="middle" fill="#68645e" font-family="Arial,sans-serif" font-size="24">contexto visual provisório</text>
    </svg>
  `)}`
});
