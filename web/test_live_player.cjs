const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(__dirname + '/dashboard_app/templates/dashboard_app/live.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
let now = 1000, interval, timeout, pagehide;
const handlers = {};
const status = {textContent: ''};
const video = {paused:false, currentTime:0,
    addEventListener: (name, handler) => handlers[name] = handler,
    play: () => Promise.resolve()};
const instances = [];
class Hls {
    static Events = {MEDIA_ATTACHED:'attached', MANIFEST_PARSED:'parsed', ERROR:'error'};
    static isSupported() { return true; }
    constructor() { this.events = {}; instances.push(this); }
    on(name, handler) { this.events[name] = handler; }
    attachMedia() { this.events.attached(); }
    loadSource(url) { this.url = url; }
    destroy() { this.destroyed = true; }
}
vm.runInNewContext(script, {Hls, document:{getElementById: id => id === 'live-video' ? video : status},
    Date:{now:() => now}, window:{addEventListener: (name, fn) => pagehide = fn},
    setTimeout: fn => {timeout = fn; return 1;}, clearTimeout:()=>{},
    setInterval: fn => {interval = fn; return 2;}, clearInterval:()=>{}});
assert.equal(status.textContent, 'Connecting...');
handlers.timeupdate();
assert.equal(status.textContent, 'Live');
now += 21000;
interval();
assert.equal(status.textContent, 'Reconnecting to live camera...');
timeout();
assert.equal(instances.length, 2);
assert.equal(instances[0].destroyed, true);
assert.notEqual(instances[0].url, instances[1].url);
video.paused = true;
handlers.pause();
now += 21000;
interval();
assert.equal(status.textContent, 'Paused');
instances[1].events.error(null, {fatal:true});
assert.equal(status.textContent, 'Reconnecting to live camera...');
pagehide();
assert.equal(instances[1].destroyed, true);
console.log('PASS: playback status, stall recovery, fresh session, pause, fatal error, cleanup');
