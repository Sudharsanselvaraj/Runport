import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'

// Small dark illustrations for the "Run it anywhere" cards: a laptop, an
// isometric container cube, a CI badge and a dashed cloud. Shapes are drawn
// here; the Docker and GitHub Actions marks are Simple Icons (CC0) files.

const LOGOS = '/assets/landing/logos'

export const LaptopArt: React.FC = () => {
  const reduce = useReducedMotion()
  return (
    <svg viewBox="0 0 220 150" className="rp-ra-art" aria-hidden="true">
      <defs>
        <linearGradient id="ra-screen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1b1b1d" />
          <stop offset="1" stopColor="#0d0d0e" />
        </linearGradient>
      </defs>
      <rect x="38" y="22" width="144" height="94" rx="6" fill="url(#ra-screen)" stroke="rgba(255,255,255,0.18)" />
      <rect x="44" y="28" width="132" height="82" rx="3" fill="#0a0a0b" stroke="rgba(255,255,255,0.05)" />
      <path d="M22 118 H198 L192 126 H28 Z" fill="#18181a" stroke="rgba(255,255,255,0.16)" />
      <rect x="96" y="118" width="28" height="3" rx="1.5" fill="rgba(255,255,255,0.12)" />
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i}
          cx={100 + i * 10}
          cy={69}
          r={2.6}
          fill="#ffffff"
          initial={{ opacity: reduce ? 0.9 : 0.25 }}
          animate={reduce ? { opacity: 0.9 } : { opacity: [0.25, 1, 0.25] }}
          transition={reduce ? undefined : { duration: 1.4, repeat: Infinity, delay: i * 0.2, ease: 'easeInOut' }}
        />
      ))}
    </svg>
  )
}

export const CubeArt: React.FC = () => {
  const reduce = useReducedMotion()
  // Isometric cube: the top face is the diamond (54,48)-(110,18)-(166,48)-(110,78).
  // The logo's 24x24 box is mapped onto the middle 60% of that face.
  return (
    <svg viewBox="0 0 220 150" className="rp-ra-art" aria-hidden="true">
      <motion.g
        animate={reduce ? undefined : { y: [0, -4, 0] }}
        transition={reduce ? undefined : { duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      >
        <polygon points="54,48 110,78 110,138 54,108" fill="#101012" stroke="rgba(255,255,255,0.16)" />
        <polygon points="110,78 166,48 166,108 110,138" fill="#0b0b0c" stroke="rgba(255,255,255,0.16)" />
        <polygon points="54,48 110,18 166,48 110,78" fill="#1c1c1f" stroke="rgba(255,255,255,0.22)" />
        <image href={`${LOGOS}/docker.svg`} width="24" height="24" transform="matrix(1.4 -0.75 1.4 0.75 76.4 48)" />
      </motion.g>
    </svg>
  )
}

const hex = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 2
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`
  }).join(' ')

export const BadgeArt: React.FC = () => {
  const reduce = useReducedMotion()
  return (
    <svg viewBox="0 0 220 150" className="rp-ra-art" aria-hidden="true">
      <polygon points={hex(110, 75, 64)} fill="#0e0e10" stroke="rgba(255,255,255,0.14)" />
      <polygon points={hex(110, 75, 50)} fill="#161618" stroke="rgba(255,255,255,0.1)" />
      <motion.circle
        cx="110"
        cy="75"
        r="36"
        fill="none"
        stroke="rgba(255,255,255,0.22)"
        strokeDasharray="3 6"
        style={{ originX: '110px', originY: '75px' }}
        animate={reduce ? undefined : { rotate: 360 }}
        transition={reduce ? undefined : { duration: 24, repeat: Infinity, ease: 'linear' }}
      />
      <image href={`${LOGOS}/githubactions.svg`} x="92" y="57" width="36" height="36" />
    </svg>
  )
}

export const CloudArt: React.FC = () => {
  const reduce = useReducedMotion()
  return (
    <svg viewBox="0 0 240 130" className="rp-ra-cloud" aria-hidden="true">
      <motion.path
        d="M62 108 C36 108 28 82 46 70 C40 48 62 34 82 42 C90 18 128 12 142 36 C160 26 184 36 182 58 C204 60 212 84 196 98 C190 105 182 108 172 108 Z"
        fill="none"
        stroke="rgba(0,0,0,0.32)"
        strokeWidth="1.4"
        strokeDasharray="5 5"
        animate={reduce ? undefined : { strokeDashoffset: [0, -40] }}
        transition={reduce ? undefined : { duration: 3, repeat: Infinity, ease: 'linear' }}
      />
      <rect x="84" y="62" width="76" height="22" rx="6" fill="#f7f7f5" stroke="rgba(0,0,0,0.28)" />
      <text x="122" y="77" textAnchor="middle" fontFamily="'Intel One Mono', ui-monospace, monospace" fontSize="10.5" letterSpacing="1.2" fill="rgba(0,0,0,0.62)">
        NO CLOUD
      </text>
    </svg>
  )
}
