import React from 'react'

/** The one label used on every mockup that shows invented numbers. */
export const SampleChip: React.FC<{ className?: string }> = ({ className }) => (
  <span className={`rp-sample-chip${className ? ` ${className}` : ''}`}>Sample data</span>
)
