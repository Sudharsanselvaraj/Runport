import fs from 'node:fs';
import path from 'node:path';

const IMAGES = {
  'hero-bg.png': 'https://framerusercontent.com/images/vKX7FekavI1DzTszCiQcPX5bF4.png?width=2400',
  'testimonial-bg.jpg': 'https://framerusercontent.com/images/e3z05tULuMdBIZA3K4LhZVdtdYY.jpeg?width=800',
  'pricing-1.jpg': 'https://framerusercontent.com/images/6uLbVwqKmZJeMmEPqJzAhSjcQ.jpeg?width=800',
  'pricing-2.png': 'https://framerusercontent.com/images/1Sd4JiuEeBSsrR1F852PxWaPsY.png?width=800',
  'pricing-3.jpg': 'https://framerusercontent.com/images/SJvyWZG5wDrX7d3eg07XR8U16ec.jpeg?width=800',
};

async function download() {
  const dir = 'web/landing/public/assets/landing';
  fs.mkdirSync(dir, { recursive: true });

  for (const [filename, url] of Object.entries(IMAGES)) {
    const dest = path.join(dir, filename);
    if (fs.existsSync(dest) && fs.statSync(dest).size > 1000) {
      console.log(`Already exists: ${filename}`);
      continue;
    }
    console.log(`Downloading ${filename} from ${url}...`);
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const buffer = Buffer.from(await resp.arrayBuffer());
      fs.writeFileSync(dest, buffer);
      console.log(`Saved ${filename} (${buffer.length} bytes)`);
    } catch (e) {
      console.error(`Failed ${filename}:`, e.message);
    }
  }
}

download();

