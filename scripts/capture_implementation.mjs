import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9223; // use 9223 to avoid conflicts
const TARGET_URL = 'http://127.0.0.1:8000/';

const VIEWPORTS = [
  { name: 'desktop_1440x900', width: 1440, height: 900, mobile: false },
  { name: 'desktop_1280x800', width: 1280, height: 800, mobile: false },
  { name: 'tablet_1024x768', width: 1024, height: 768, mobile: false },
  { name: 'tablet_portrait_768x1024', width: 768, height: 1024, mobile: false },
  { name: 'mobile_390x844', width: 390, height: 844, mobile: true, dsf: 2 },
  { name: 'mobile_375x812', width: 375, height: 812, mobile: true, dsf: 2 },
];

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  const outputDir = path.resolve('docs/implementation_screenshots');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  console.log('Launching Headless Chrome for Implementation Capture...');
  const chromeProcess = spawn(CHROME_PATH, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--disable-gpu',
    '--hide-scrollbars',
    '--no-first-run',
    '--no-default-browser-check',
    '--user-data-dir=/tmp/chrome_cdp_profile_impl',
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
    await send('CSS.enable');

    console.log(`Navigating to ${TARGET_URL}...`);
    await send('Page.navigate', { url: TARGET_URL });
    await sleep(2500);

    for (const vp of VIEWPORTS) {
      console.log(`Setting viewport: ${vp.name} (${vp.width}x${vp.height})...`);
      await send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: vp.dsf || 1,
        mobile: vp.mobile,
      });
      await send('Emulation.setTouchEmulationEnabled', { enabled: vp.mobile });
      await sleep(1000);

      // Viewport screenshot
      const vpScreenshot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(
        path.join(outputDir, `${vp.name}_viewport.png`),
        Buffer.from(vpScreenshot.data, 'base64')
      );

      // Full page screenshot
      const metrics = await send('Page.getLayoutMetrics');
      const contentHeight = Math.ceil(metrics.contentSize.height);
      const contentWidth = Math.ceil(metrics.contentSize.width);

      await send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: contentHeight,
        deviceScaleFactor: vp.dsf || 1,
        mobile: vp.mobile,
      });
      await sleep(1000);

      const fullScreenshot = await send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: true,
      });
      fs.writeFileSync(
        path.join(outputDir, `${vp.name}_full.png`),
        Buffer.from(fullScreenshot.data, 'base64')
      );

      // Reset height
      await send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: vp.dsf || 1,
        mobile: vp.mobile,
      });
      await sleep(500);
    }

    console.log('Capturing section slices on desktop 1440x900...');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(500);

    const sliceYPositions = [0, 800, 1600, 2400, 3200, 4000, 4800, 5600, 6400];
    for (let i = 0; i < sliceYPositions.length; i++) {
      const y = sliceYPositions[i];
      await send('Runtime.evaluate', {
        expression: `window.scrollTo(0, ${y})`,
      });
      await sleep(600);
      const sliceShot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(
        path.join(outputDir, `slice_${i + 1}_y${y}.png`),
        Buffer.from(sliceShot.data, 'base64')
      );
    }

    console.log('Testing interactive modal or workbench toggle...');
    // Click on launch workbench
    await send('Runtime.evaluate', {
      expression: `document.querySelector('a[href="#workbench"]')?.click()`,
    });
    await sleep(1000);
    const workbenchShot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(
      path.join(outputDir, `workbench_view.png`),
      Buffer.from(workbenchShot.data, 'base64')
    );

    console.log('All implementation screenshots captured successfully!');
    ws.close();
  } catch (err) {
    console.error('Error during capture:', err);
  } finally {
    chromeProcess.kill();
  }
}

main().catch(console.error);

