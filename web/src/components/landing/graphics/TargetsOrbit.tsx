import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Globe } from 'lucide-react'
import { STATUS_LABEL } from '../../../data/connectors'
import { useLoopWhenVisible, useRafLoop } from '../motionKit'
import { ellipsePoint, orbitAngle, orbitTiles, type OrbitTile } from './frames'

// Card 1: the Runport emblem inside two tilted elliptical rings. Every target
// connector from data/connectors.ts travels slowly on a ring (supported on the
// outer ring, experimental on the inner one). Hovering or focusing a tile
// pauses the orbit and shows its name and status. Positions are written straight
// to the DOM each frame; reduced motion keeps the tiles at their start angles.

const TILT = (-14 * Math.PI) / 180
const rot = (x: number, y: number) => ({ x: x * Math.cos(TILT) - y * Math.sin(TILT), y: x * Math.sin(TILT) + y * Math.cos(TILT) })

export const TargetsOrbit: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const tileRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [box, setBox] = useState({ w: 360, h: 240 })
  const [hover, setHover] = useState<string | null>(null)
  const tiles = useMemo(orbitTiles, [])
  const { active, reduced } = useLoopWhenVisible(ref)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const radii = (ring: 0 | 1) => {
    const rx = Math.min(box.w * 0.46, 260) * (ring === 1 ? 1 : 0.62)
    const ry = Math.min(box.h * 0.3, 100) * (ring === 1 ? 1 : 0.62)
    return { rx, ry }
  }

  const tRef = useRef(0)
  const place = (t: number) => {
    tRef.current = t
    tiles.forEach((tile: OrbitTile, i) => {
      const el = tileRefs.current[i]
      if (!el) return
      const { rx, ry } = radii(tile.ring)
      const p = ellipsePoint(orbitAngle(tile, t, reduced), rx, ry)
      const q = rot(p.x, p.y)
      // tiles behind the emblem (upper half of the ellipse) sit lower and dimmer
      const behind = p.y < 0
      el.style.transform = `translate(${q.x.toFixed(1)}px, ${(q.y + 6).toFixed(1)}px) scale(${behind ? 0.86 : 1})`
      el.style.zIndex = behind ? '1' : '3'
      el.style.opacity = behind ? '0.7' : '1'
    })
  }
  useRafLoop(active && hover === null, place)
  // keep tiles on the rings when the card resizes while the loop is stopped
  useEffect(() => place(tRef.current), [box, reduced]) // eslint-disable-line react-hooks/exhaustive-deps

  const outer = radii(1)
  const inner = radii(0)
  const cx = box.w / 2
  const cy = box.h / 2 + 6
  const tiltDeg = (TILT * 180) / Math.PI

  return (
    <div ref={ref} className="rp-g-orbit" role="group" aria-label="Target connectors, orbiting Runport">
      <svg className="rp-g-orbit-rings" width={box.w} height={box.h} aria-hidden="true">
        <ellipse cx={cx} cy={cy} rx={outer.rx} ry={outer.ry} transform={`rotate(${tiltDeg} ${cx} ${cy})`} />
        <ellipse cx={cx} cy={cy} rx={inner.rx} ry={inner.ry} transform={`rotate(${tiltDeg} ${cx} ${cy})`} />
      </svg>
      <div className="rp-g-orbit-core" aria-hidden="true" style={{ marginTop: -28 }}>
        <img src="/assets/landing/runport-emblem.png" alt="" width={44} height={44} />
      </div>
      {tiles.map((tile, i) => (
        <button
          key={tile.id}
          type="button"
          ref={(el) => (tileRefs.current[i] = el)}
          className={`rp-g-tile is-${tile.status}${hover === tile.id ? ' is-hover' : ''}`}
          aria-label={`${tile.name}: ${STATUS_LABEL[tile.status]} connector`}
          onPointerEnter={() => setHover(tile.id)}
          onPointerLeave={() => setHover(null)}
          onFocus={() => setHover(tile.id)}
          onBlur={() => setHover(null)}
        >
          <span className="rp-g-tile-face">
            {tile.logo ? <img src={tile.logo} alt="" width={16} height={16} loading="lazy" /> : <Globe size={15} aria-hidden="true" />}
            <i className="rp-g-tile-dot" aria-hidden="true" />
          </span>
          <span className="rp-g-tip" aria-hidden="true">
            {tile.name}
            <em>{STATUS_LABEL[tile.status]}</em>
          </span>
        </button>
      ))}
      <p className="rp-g-orbit-legend" aria-hidden="true">
        <span><i className="is-supported" />Supported</span>
        <span><i className="is-experimental" />Experimental</span>
      </p>
    </div>
  )
}
