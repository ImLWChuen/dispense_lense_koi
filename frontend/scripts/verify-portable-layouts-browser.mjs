/**
 * Browser smoke test for the DLK-M3-046 portable-layout workflow.
 *
 * Uses real Chromium file inputs and downloads. The API result is captured
 * from DevTools network events; an unavailable backend is reported separately
 * from the UI checks and does not get misreported as a successful round trip.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const frontendUrl = "http://localhost:3001/diagnosis/new";
const backendUrl = "http://127.0.0.1:8000";
const tempRoot = path.join(os.tmpdir(), `dlk046-browser-${Date.now()}`);
const downloadDir = path.join(tempRoot, "downloads");
const userDataDir = path.join(tempRoot, "chrome-profile");
fs.mkdirSync(downloadDir, { recursive: true });
fs.mkdirSync(userDataDir, { recursive: true });

class CdpClient {
    constructor(url) {
        this.socket = new WebSocket(url);
        this.nextId = 1;
        this.pending = new Map();
        this.listeners = new Map();
        this.ready = new Promise((resolve, reject) => {
            this.socket.onopen = resolve;
            this.socket.onerror = reject;
        });
        this.socket.onmessage = ({ data }) => {
            const message = JSON.parse(data);
            if (message.id && this.pending.has(message.id)) {
                const waiter = this.pending.get(message.id);
                this.pending.delete(message.id);
                if (message.error) waiter.reject(new Error(JSON.stringify(message.error)));
                else waiter.resolve(message.result);
            } else if (message.method) {
                for (const listener of this.listeners.get(message.method) ?? []) listener(message.params);
            }
        };
    }

    async send(method, params = {}) {
        await this.ready;
        const id = this.nextId++;
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.socket.send(JSON.stringify({ id, method, params }));
        });
    }

    on(method, listener) {
        const list = this.listeners.get(method) ?? [];
        list.push(listener);
        this.listeners.set(method, list);
    }

    async evaluate(expression) {
        const result = await this.send("Runtime.evaluate", {
            expression,
            awaitPromise: true,
            returnByValue: true,
        });
        if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
        return result.result?.value;
    }

    close() { this.socket.close(); }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(evaluate, predicate, label, timeoutMs = 10000) {
    const until = Date.now() + timeoutMs;
    let lastValue;
    while (Date.now() < until) {
        lastValue = await evaluate();
        if (predicate(lastValue)) return lastValue;
        await sleep(250);
    }
    throw new Error(`Timed out waiting for ${label}; last value: ${JSON.stringify(lastValue)}`);
}

async function setFileInput(cdp, selector, filePath) {
    const { root } = await cdp.send("DOM.getDocument", { depth: -1 });
    const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector });
    assert.ok(nodeId, `File input not found: ${selector}`);
    await cdp.send("DOM.setFileInputFiles", { nodeId, files: [filePath] });
    await cdp.evaluate(`document.querySelector(${JSON.stringify(selector)}).dispatchEvent(new Event("change", { bubbles: true }))`);
}

async function clickButton(cdp, fragment, occurrence = 0) {
    const clicked = await cdp.evaluate(`(() => {
        const matches = Array.from(document.querySelectorAll("button"))
            .filter((button) => button.innerText.includes(${JSON.stringify(fragment)}));
        const button = ${occurrence} < 0 ? matches.at(${occurrence}) : matches[${occurrence}];
        if (!button || button.disabled) return { found: Boolean(button), disabled: Boolean(button?.disabled), count: matches.length };
        button.click();
        return { found: true, disabled: false, count: matches.length };
    })()`);
    assert.equal(clicked.found, true, `Button containing '${fragment}' must exist`);
    assert.equal(clicked.disabled, false, `Button containing '${fragment}' must be enabled`);
    return clicked;
}

async function run() {
    assert.ok(fs.existsSync(chromePath), `Chrome not found at ${chromePath}`);
    const repoRoot = path.resolve("..");
    const imageA = path.join(repoRoot, "scratch", "part_a_two_site.png");
    const imageB = path.join(repoRoot, "scratch", "part_b_mismatch.png");
    assert.ok(fs.existsSync(imageA), `Missing synthetic fixture: ${imageA}`);
    assert.ok(fs.existsSync(imageB), `Missing synthetic fixture: ${imageB}`);

    const chrome = spawn(chromePath, [
        "--headless=new", "--no-sandbox", "--disable-gpu", "--window-size=1440,1000",
        "--remote-debugging-port=0", `--user-data-dir=${userDataDir}`,
        `--download-default-directory=${downloadDir}`, frontendUrl,
    ], { stdio: ["ignore", "ignore", "pipe"] });
    let cdp;
    try {
        const port = await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error("Chrome DevTools did not start within 10 seconds")), 10000);
            chrome.stderr.on("data", (chunk) => {
                const match = chunk.toString().match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)/);
                if (match) { clearTimeout(timeout); resolve(match[1]); }
            });
            chrome.once("error", reject);
            chrome.once("exit", (code) => reject(new Error(`Chrome exited before DevTools was ready (${code})`)));
        });
        await sleep(500);
        const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
        const page = targets.find((target) => target.type === "page" && target.url.includes("3001"));
        assert.ok(page, "Chrome page for the DispenseIQ diagnosis route must be open");
        cdp = new CdpClient(page.webSocketDebuggerUrl);
        await cdp.ready;
        await cdp.send("Page.enable");
        await cdp.send("DOM.enable");
        await cdp.send("Runtime.enable");
        await cdp.send("Network.enable");
        await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: downloadDir });

        const requests = [];
        const responses = new Map();
        const failures = new Map();
        cdp.on("Network.requestWillBeSent", (event) => {
            if (event.request.url === `${backendUrl}/api/v1/images/analyze` && event.request.method === "POST") {
                requests.push({ requestId: event.requestId, url: event.request.url, method: event.request.method, postData: event.request.postData ?? null });
            }
        });
        cdp.on("Network.responseReceived", (event) => responses.set(event.requestId, event.response.status));
        cdp.on("Network.loadingFailed", (event) => failures.set(event.requestId, event.errorText));

        await waitFor(() => cdp.evaluate("document.readyState"), (value) => value === "complete", "diagnosis page load");
        const imageInput = 'input[type="file"][accept*="image"]';
        const layoutInput = 'input[type="file"][aria-label="Upload portable region layout JSON"]';

        // Upload source image and save through the actual dialog/download path.
        await setFileInput(cdp, imageInput, imageA);
        await waitFor(() => cdp.evaluate(`(() => {
            const image = document.querySelector('img[alt="Deposit target"]');
            const save = Array.from(document.querySelectorAll("button")).find((button) => button.innerText.includes("Save layout"));
            return { width: image?.naturalWidth ?? 0, height: image?.naturalHeight ?? 0, saveEnabled: Boolean(save && !save.disabled) };
        })()`), (value) => value.width === 800 && value.height === 600 && value.saveEnabled, "decoded source dimensions and enabled save action");
        await clickButton(cdp, "Save layout");
        await waitFor(() => cdp.evaluate("Boolean(document.querySelector('#layout-name-input'))"), Boolean, "save-layout dialog");
        await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape" });
        await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape" });
        await waitFor(() => cdp.evaluate("!document.querySelector('#layout-name-input')"), Boolean, "Escape to close save dialog");
        await clickButton(cdp, "Save layout");
        await waitFor(() => cdp.evaluate("Boolean(document.querySelector('#layout-name-input'))"), Boolean, "save dialog reopening");
        await cdp.evaluate("document.querySelector('#layout-name-input').focus()");
        await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter" });
        await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter" });
        const layoutPath = path.join(downloadDir, "dispense-region-layout.json");
        await waitFor(() => fs.existsSync(layoutPath), Boolean, "actual browser JSON download", 5000);
        const savedLayout = JSON.parse(fs.readFileSync(layoutPath, "utf8"));
        assert.deepEqual(Object.keys(savedLayout).sort(), ["format", "name", "rois", "source_image", "version"]);
        assert.deepEqual(savedLayout.source_image, { width: 800, height: 600 });
        assert.equal(savedLayout.rois.length, 1);
        assert.deepEqual(Object.keys(savedLayout.rois[0]).sort(), ["height", "roi_id", "width", "x", "y"]);
        console.log(`PASS saved/downloaded real layout: ${layoutPath}; ${savedLayout.rois.length} ROI`);

        // Upload target image, submit a real invalid file, then re-import the downloaded file.
        await setFileInput(cdp, imageInput, imageB);
        await waitFor(() => cdp.evaluate(`(() => { const image = document.querySelector('img[alt="Deposit target"]'); return {width:image?.naturalWidth ?? 0,height:image?.naturalHeight ?? 0}; })()`), (value) => value.width === 1024 && value.height === 768, "decoded target dimensions");
        const invalidFile = path.join(downloadDir, "invalid-layout.json");
        fs.writeFileSync(invalidFile, "{ not valid json");
        await setFileInput(cdp, layoutInput, invalidFile);
        const invalidState = await waitFor(() => cdp.evaluate(`({ text: document.body.innerText, pending: document.body.innerText.includes("Pending Region Placement Confirmation") })`), (value) => /invalid JSON syntax/i.test(value.text), "invalid-file error banner");
        assert.equal(invalidState.pending, false, "Invalid file must not alter layout state");
        console.log("PASS invalid JSON is rejected without importing regions");

        const postsBeforeImport = requests.length;
        await setFileInput(cdp, layoutInput, layoutPath);
        const pendingState = await waitFor(() => cdp.evaluate(`(() => {
            const text = document.body.innerText;
            const button = Array.from(document.querySelectorAll("button")).filter((candidate) => candidate.innerText.trim().startsWith("Analyze")).at(-1);
            return { text, disabled: Boolean(button?.disabled) };
        })()`), (value) => value.text.includes("Pending Region Placement Confirmation") && value.disabled, "unconfirmed imported layout and disabled Analyze");
        assert.match(pendingState.text, /800 × 600 px[\s\S]*1024 × 768 px/);
        assert.match(pendingState.text, /Dimension mismatch detected/);
        const countBeforeBlockedClick = requests.length;
        await cdp.evaluate(`(() => Array.from(document.querySelectorAll("button")).filter((candidate) => candidate.innerText.trim().startsWith("Analyze")).at(-1)?.click())()`);
        await sleep(500);
        assert.equal(requests.length, countBeforeBlockedClick, "No analysis request may dispatch while imported placement is unconfirmed");
        console.log(`PASS real-file re-import, mismatch notice, and no analysis dispatch before confirmation (pre-import POSTs: ${postsBeforeImport})`);

        await clickButton(cdp, "Confirm region placement");
        await waitFor(() => cdp.evaluate("document.body.innerText.includes('Region Placement Confirmed')"), Boolean, "placement confirmation");
        const beforeAnalysis = requests.length;
        await clickButton(cdp, "Analyze", -1);
        await waitFor(() => Promise.resolve(requests.length), (count) => count > beforeAnalysis, "confirmed analysis POST", 5000);
        const capturedRequest = requests.at(-1);
        await waitFor(
            () => Promise.resolve(responses.has(capturedRequest.requestId) || failures.has(capturedRequest.requestId)),
            Boolean,
            "analysis HTTP response or network failure",
            15000,
        );
        const apiStatus = responses.get(capturedRequest.requestId) ?? null;
        const apiFailure = failures.get(capturedRequest.requestId) ?? null;
        let postData = capturedRequest.postData;
        if (!postData) {
            try { postData = (await cdp.send("Network.getRequestPostData", { requestId: capturedRequest.requestId })).postData; } catch { /* Request may have failed before body retrieval. */ }
        }
        console.log(`LIVE_API request=${capturedRequest.method} ${capturedRequest.url} status=${apiStatus ?? "unavailable"} failure=${apiFailure ?? "none"} submitted_roi_id=${String(postData ?? "").includes(savedLayout.rois[0].roi_id)}`);
        assert.ok(String(postData ?? "").includes(savedLayout.rois[0].roi_id), "Confirmed request must submit the saved ROI ID");

        // The Studio view shares the same upload state and therefore the same confirmation.
        await clickButton(cdp, "Expand Studio");
        const studioState = await waitFor(() => cdp.evaluate(`(() => {
            const modal = Array.from(document.querySelectorAll("div.fixed")).find((node) => node.innerText.includes("Computer Vision Defect Studio"));
            return { visible: Boolean(modal), confirmed: Boolean(modal?.innerText.includes("Region Placement Confirmed")), layoutControls: Boolean(modal?.innerText.includes("Save layout") && modal?.innerText.includes("Load layout")) };
        })()`), (value) => value.visible && value.confirmed && value.layoutControls, "Studio parity for imported confirmation");
        console.log(`PASS Studio mirrors confirmation and layout controls: ${JSON.stringify(studioState)}`);

        // Draw a new region in Studio and verify that shared state invalidates confirmation.
        const drawMode = await cdp.evaluate(`(() => {
            const modal = Array.from(document.querySelectorAll("div.fixed")).find((node) => node.innerText.includes("Computer Vision Defect Studio"));
            const draw = Array.from(modal?.querySelectorAll('[role="radio"]') ?? []).find((button) => button.innerText.includes("Draw ROI"));
            if (!draw || draw.disabled) return { found: Boolean(draw), disabled: Boolean(draw?.disabled), checked: draw?.getAttribute("aria-checked") };
            draw.click();
            return { found: true, disabled: false, checked: draw.getAttribute("aria-checked") };
        })()`);
        assert.equal(drawMode.found, true, "Studio Draw ROI control must exist and be enabled");
        const imageRect = await cdp.evaluate(`(() => {
            const modal = Array.from(document.querySelectorAll("div.fixed")).find((node) => node.innerText.includes("Computer Vision Defect Studio"));
            const image = modal?.querySelector('img[alt="Deposit target"]');
            if (!image) return null;
            const rect = image.getBoundingClientRect();
            return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        })()`);
        assert.ok(imageRect?.width > 0 && imageRect?.height > 0, "Studio target image must be measurable for an edit");
        const startX = imageRect.x + imageRect.width * 0.88;
        const startY = imageRect.y + imageRect.height * 0.10;
        const endX = imageRect.x + imageRect.width * 0.98;
        const endY = imageRect.y + imageRect.height * 0.24;
        await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: startX, y: startY, button: "left", buttons: 1 });
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: endX, y: endY, button: "left", buttons: 1 });
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: endX, y: endY, button: "left", buttons: 0 });
        const edited = await waitFor(() => cdp.evaluate(`(() => {
            const text = document.body.innerText;
            const modal = Array.from(document.querySelectorAll("div.fixed")).find((node) => node.innerText.includes("Computer Vision Defect Studio"));
            const run = Array.from(modal?.querySelectorAll("button") ?? []).find((button) => button.innerText.includes("Run CV Analysis"));
            return { pending: text.includes("Pending Region Placement Confirmation"), confirmed: text.includes("Region Placement Confirmed"), runDisabled: Boolean(run?.disabled) };
        })()`), (value) => value.pending && !value.confirmed && value.runDisabled, "Studio edit invalidation of confirmation");
        console.log(`PASS Studio ROI edit invalidates placement confirmation: ${JSON.stringify(edited)}`);

        await clickButton(cdp, "Abandon & Draw Manually");
        const abandoned = await cdp.evaluate(`({ pending: document.body.innerText.includes("Pending Region Placement Confirmation"), confirmed: document.body.innerText.includes("Region Placement Confirmed"), regionCountLabels: Array.from(document.querySelectorAll("span")).filter((node) => /\d+ defined/.test(node.innerText)).map((node) => node.innerText) })`);
        assert.equal(abandoned.pending, false, "Manual fallback should remove the pending-placement gate");
        assert.equal(abandoned.confirmed, false, "Manual fallback should clear imported-layout confirmation");
        console.log(`PASS manual abandonment clears imported layout gate: ${JSON.stringify(abandoned)}`);

        if (apiStatus === 200) {
            const response = await cdp.send("Network.getResponseBody", { requestId: capturedRequest.requestId });
            const responseText = response.base64Encoded ? Buffer.from(response.body, "base64").toString("utf8") : response.body;
            const parsed = JSON.parse(responseText);
            const ids = Array.isArray(parsed.roi_measurements) && parsed.roi_measurements.some((row) => row.roi_id === savedLayout.rois[0].roi_id);
            assert.ok(ids, "Live analysis response must contain a measurement for the submitted ROI ID");
            console.log(`LIVE_API_RESPONSE status=200 saved_roi_id_in_response=${ids} body=${responseText.slice(0, 1200)}`);
        } else {
            console.log("LIVE_API_BLOCKED: confirmed request was dispatched, but no HTTP 200 response was received; service preflight is required for acceptance.");
        }
        return apiStatus === 200;
    } finally {
        cdp?.close();
        chrome.kill();
    }
}

run().then((liveApiPassed) => {
    console.log(liveApiPassed ? "BROWSER_RESULT=PASS" : "BROWSER_RESULT=UI_PASS_LIVE_API_BLOCKED");
}).catch((error) => {
    console.error(`BROWSER_RESULT=FAIL ${error.stack ?? error}`);
    process.exitCode = 1;
});
