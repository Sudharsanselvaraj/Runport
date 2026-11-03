import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9222;

const VIEWPORTS = [
  { name: 'desktop_1440x900', width: 1440, height: 900, mobile: false },
  { name: 'desktop_1280x800', width: 1280, height: 800, mobile: false },
  { name: 'tablet_1024x768', width: 1024, height: 768, mobile: false },
  { name: 'tablet_portrait_768x1024', width: 768, height: 1024, mobile: false },
  { name: 'mobile_390x844', width: 390, height: 844, mobile: true, dsf: 3 },
  { name: 'mobile_375x812', width: 375, height: 812, mobile: true, dsf: 3 },
];

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  console.log('Launching Headless Chrome...');
  const chromeProcess = spawn(CHROME_PATH, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--disable-gpu',
    '--hide-scrollbars',
    '--no-first-run',
    '--no-default-browser-check',
    '--user-data-dir=/tmp/chrome_cdp_profile_audit',
  ]);

  await sleep(1500);

  try {
    const listResp = await fetch(`http://127.0.0.1:${PORT}/json/new`, { method: 'PUT' });
    const target = await listResp.json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);

    let id = 1;
    const callbacks = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && callbacks.has(msg.id)) {
        const { resolve, reject } = callbacks.get(msg.id);
        callbacks.delete(msg.id);
        if (msg.error) reject(msg.error);
        else resolve(msg.result);
      }
    };

    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    function send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const msgId = id++;
        callbacks.set(msgId, { resolve, reject });
        ws.send(JSON.stringify({ id: msgId, method, params }));
      });
    }

    await send('Page.enable');
    await send('DOM.enable');
    await send('Runtime.enable');

    console.log('Loading reference site...');
    await send('Page.navigate', { url: 'https://getpulse.framer.website/' });
    await sleep(4000);

    // Scroll through the entire page slowly to trigger Framer scroll reveals and lazy loads
    console.log('Triggering scroll reveals and lazy loading...');
    await send('Runtime.evaluate', {
      expression: `(async () => {
        const total = document.documentElement.scrollHeight;
        for (let y = 0; y < total; y += 400) {
          window.scrollTo(0, y);
          await new Promise(r => setTimeout(r, 100));
        }
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 500));
      })()`,
      awaitPromise: true,
    });

    // 1. Capture at all required viewports
    for (const vp of VIEWPORTS) {
      console.log(`Capturing viewport: ${vp.name} (${vp.width}x${vp.height})...`);
      await send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: vp.dsf || 1,
        mobile: vp.mobile,
      });
      await sleep(1000);

      // Initial viewport (above fold)
      const vpShot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(`docs/reference_screenshots/${vp.name}_viewport.png`, Buffer.from(vpShot.data, 'base64'));

      // Full page
      const fullShot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
      fs.writeFileSync(`docs/reference_screenshots/${vp.name}_full.png`, Buffer.from(fullShot.data, 'base64'));
    }

    // Reset to desktop 1440
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(500);

    // Extract deep DOM inspection data
    console.log('Extracting design tokens, DOM hierarchy, and typography...');
    const inspectionData = await send('Runtime.evaluate', {
      expression: `(() => {
        function getStyles(el) {
          if (!el) return null;
          const s = window.getComputedStyle(el);
          return {
            fontFamily: s.fontFamily,
            fontSize: s.fontSize,
            fontWeight: s.fontWeight,
            lineHeight: s.lineHeight,
            letterSpacing: s.letterSpacing,
            color: s.color,
            backgroundColor: s.backgroundColor,
            backgroundImage: s.backgroundImage.slice(0, 100),
            borderColor: s.borderColor,
            borderRadius: s.borderRadius,
            boxShadow: s.boxShadow,
            backdropFilter: s.backdropFilter,
            padding: s.padding,
            margin: s.margin,
            width: s.width,
            height: s.height,
            display: s.display,
            gap: s.gap,
            maxWidth: s.maxWidth
          };
        }

        const bodyStyles = getStyles(document.body);

        // Find main sections or container blocks
        const main = document.querySelector('main') || document.body;
        const allElements = Array.from(document.querySelectorAll('*'));

        // Collect all images
        const images = Array.from(document.querySelectorAll('img')).map(img => ({
          src: img.src,
          alt: img.alt,
          width: img.offsetWidth,
          height: img.offsetHeight,
          naturalWidth: img.naturalWidth,
          naturalHeight: img.naturalHeight,
          styles: getStyles(img)
        }));

        // Collect all buttons and links
        const buttons = Array.from(document.querySelectorAll('button, a')).map(b => ({
          text: (b.innerText || '').trim().slice(0, 60),
          tag: b.tagName,
          href: b.getAttribute('href'),
          width: b.offsetWidth,
          height: b.offsetHeight,
          styles: getStyles(b)
        })).filter(b => b.text && b.width > 0);

        // Collect headings
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, p')).map(h => ({
          tag: h.tagName,
          text: (h.innerText || '').trim(),
          styles: getStyles(h),
          rect: h.getBoundingClientRect()
        })).filter(h => h.text.length > 0 && h.rect.width > 0);

        // Extract colors found
        const colors = new Set();
        const fontFamilies = new Set();
        allElements.forEach(el => {
          const s = window.getComputedStyle(el);
          if (s.color) colors.add(s.color);
          if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)') colors.add(s.backgroundColor);
          if (s.borderColor) colors.add(s.borderColor);
          if (s.fontFamily) fontFamilies.add(s.fontFamily);
        });

        // Top level layout blocks
        const topBlocks = Array.from(main.children).map(child => {
          const rect = child.getBoundingClientRect();
          return {
            tagName: child.tagName,
            className: child.className,
            textSnippet: (child.innerText || '').slice(0, 150).replace(/\\s+/g, ' '),
            rect: { top: rect.top + window.scrollY, left: rect.left, width: rect.width, height: rect.height },
            styles: getStyles(child)
          };
        });

        return {
          title: document.title,
          bodyStyles,
          topBlocks,
          colors: Array.from(colors),
          fontFamilies: Array.from(fontFamilies),
          images,
          buttons: buttons.slice(0, 30),
          headings: headings.slice(0, 40)
        };
      })()`,
      returnByValue: true
    });

    fs.writeFileSync('docs/landing-page-reference-raw.json', JSON.stringify(inspectionData.result.value, null, 2));
    console.log('Saved docs/landing-page-reference-raw.json');

    // Also slice the full-page screenshot into sequential sections for easy review
    console.log('Capturing section slices at 1440 width...');
    const sliceHeights = [0, 900, 1800, 2700, 3600, 4500, 5400, 6300];
    for (let i = 0; i < sliceHeights.length; i++) {
      const y = sliceHeights[i];
      await send('Runtime.evaluate', { expression: `window.scrollTo(0, ${y})` });
      await sleep(300);
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(`docs/reference_screenshots/section_slice_${i + 1}_y${y}.png`, Buffer.from(shot.data, 'base64'));
    }

    console.log('All reference screenshots and data captured successfully!');
    ws.close();
  } finally {
    chromeProcess.kill('SIGKILL');
  }
}

main().catch(console.error);
