import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Globe } from 'lucide-react'
import { STATUS_LABEL } from '../../../data/connectors'
import { useLoopWhenVisible, useRafLoop } from '../motionKit'
import { ellipsePoint, orbitAngle, orbitCaption, orbitTiles, type OrbitTile } from './frames'

// Card 1: the Runport emblem centred inside two thin elliptical rings, with
// eight connector tiles drifting slowly along them (one slot per 12 s loop,
// ease-in-out). No dots or legend on the graphic: a tile's name and status show
// only in a tooltip on hover or keyboard focus. Hovering the graphic pauses the
// orbit. One muted caption below, computed from the connector data file.

const TILT = (-12 * Math.PI) / 180
const rot = (x: number, y: number) => ({ x: x * Math.cos(TILT) - y * Math.sin(TILT), y: x * Math.sin(TILT) + y * Math.cos(TILT) })

export const TargetsOrbit: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const tileRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [box, setBox] = useState({ w: 480, h: 200 })
  const [hold, setHold] = useState(false)
  const [tip, setTip] = useState<string | null>(null)
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
    const rx = Math.min(box.w * 0.44, 230) * (ring === 1 ? 1 : 0.6)
    const ry = Math.max(40, box.h * 0.4 - 16) * (ring === 1 ? 1 : 0.6)
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
      el.style.transform = `translate(${q.x.toFixed(1)}px, ${q.y.toFixed(1)}px)`
      el.style.zIndex = p.y < 0 ? '1' : '3'
    })
  }
  useRafLoop(active && !hold, place)
  useEffect(() => place(tRef.current), [box, reduced]) // eslint-disable-line react-hooks/exhaustive-deps

  const outer = radii(1)
  const inner = radii(0)
  const cx = box.w / 2
  const cy = box.h / 2
  const tiltDeg = (TILT * 180) / Math.PI

  return (
    <div className="rp-g-targets">
      <div
        ref={ref}
        className="rp-g-orbit"
        role="group"
        aria-label="Connectors orbiting Runport. Focus a tile to read its status."
        onPointerEnter={() => setHold(true)}
        onPointerLeave={() => setHold(false)}
      >
        <svg className="rp-g-orbit-rings" width={box.w} height={box.h} aria-hidden="true">
          <ellipse cx={cx} cy={cy} rx={outer.rx} ry={outer.ry} transform={`rotate(${tiltDeg} ${cx} ${cy})`} />
          <ellipse cx={cx} cy={cy} rx={inner.rx} ry={inner.ry} transform={`rotate(${tiltDeg} ${cx} ${cy})`} />
        </svg>
        <div className="rp-g-orbit-core" aria-hidden="true">
          <img src="/assets/landing/runport-emblem.png" alt="" width={30} height={30} />
        </div>
        {tiles.map((tile, i) => (
          <button
            key={tile.id}
            type="button"
            ref={(el) => (tileRefs.current[i] = el)}
            className={`rp-g-tile${tip === tile.id ? ' is-tip' : ''}`}
            aria-label={`${tile.name}: ${STATUS_LABEL[tile.status]}`}
            onPointerEnter={() => setTip(tile.id)}
            onPointerLeave={() => setTip(null)}
            onFocus={() => {
              setTip(tile.id)
              setHold(true)
            }}
            onBlur={() => {
              setTip(null)
              setHold(false)
            }}
          >
            <span className="rp-g-tile-face">
              {tile.logo ? <img src={tile.logo} alt="" width={15} height={15} loading="lazy" /> : <Globe size={14} aria-hidden="true" />}
            </span>
            <span className="rp-g-tip" aria-hidden="true">
              {tile.name}
              <em className={`rp-g-pill is-${tile.status}`}>{STATUS_LABEL[tile.status]}</em>
            </span>
          </button>
        ))}
      </div>
      <p className="rp-g-caption">{orbitCaption()}</p>
    </div>
  )
}
