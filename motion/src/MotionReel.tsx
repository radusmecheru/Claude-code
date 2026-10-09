import React from 'react';
import {AbsoluteFill, Easing, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/fonts';
import {interpolatePath} from '@remotion/paths';

// Beat-driven motion-design reel (refs r1 @motionlovee and r2 @vizibilonline): every scene starts on a beat.
// Meant to be played full screen on a laptop and filmed in a dark room, or composited with
// looks.screen_insert(). Neutral demo brand; pass real names/colours via props.

const fontFamily = 'Inter';
for (const weight of ['400', '600', '800']) {
	loadFont({family: fontFamily, url: staticFile(`fonts/Inter-${weight}.ttf`), weight});
}

export type ReelProps = {
	brand: string;
	tagline: string;
	accent: string;
	words: string[];
	prompt: string;
	options: string[];
	beats: number[]; // seconds; scenes start on beats[sceneStart[i]]
};

export const reelDefaults: ReelProps = {
	brand: 'NOVA',
	tagline: 'motion designer',
	accent: '#D87657',
	words: ['EASE', 'IN.', 'EASE', 'OUT.', 'NEVER', 'LINEAR'],
	prompt: 'Show me what you can do',
	options: ['Chat', 'Studio', 'Code'],
	beats: Array.from({length: 40}, (_, i) => 0.4 + i * 0.465),
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const useU = () => {
	const {width, height} = useVideoConfig();
	return Math.min(width, height) / 1080;
};

const Center: React.FC<{children: React.ReactNode; bg?: string}> = ({children, bg}) => (
	<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', background: bg}}>{children}</AbsoluteFill>
);

// 1. Dot pulses, rings form, a spark/asterisk blooms (hook), then slams to the brand on the drop.
const Burst: React.FC<ReelProps> = ({accent, brand}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const pulse = 1 + Math.sin(f / 4) * 0.15;
	const rings = [0, 1, 2].map((i) => interpolate(f, [10 + i * 6, 40 + i * 6], [0, 1], clamp));
	const star = spring({frame: f - 30, fps, config: {damping: 10}});
	const slam = spring({frame: f - 52, fps, config: {damping: 9, stiffness: 160}});
	const flash = interpolate(f, [50, 53, 62], [0, 1, 0], clamp);
	return (
		<Center bg="#0b0b0c">
			{rings.map((r, i) => (
				<div key={i} style={{position: 'absolute', width: 600 * u * r, height: 600 * u * r, borderRadius: '50%',
					border: `${4 * u}px solid ${accent}`, opacity: (1 - r) * 0.9}} />
			))}
			<svg width={260 * u} height={260 * u} viewBox="-50 -50 100 100"
				style={{transform: `scale(${(f < 30 ? 0.12 * pulse : star) * (1 - slam * 0.85)}) rotate(${star * 90}deg)`}}>
				{Array.from({length: 6}).map((_, i) => (
					<rect key={i} x={-5} y={-48} width={10} height={44} rx={5} fill={accent} transform={`rotate(${i * 30})`} />
				))}
				<circle r={f < 30 ? 30 : 0} fill={accent} />
			</svg>
			<div style={{position: 'absolute', fontFamily, fontWeight: 800, color: 'white', fontSize: 190 * u,
				letterSpacing: `${(1 - slam) * 60 * u}px`, transform: `scaleX(${0.6 + slam * 0.4})`, opacity: slam}}>{brand}</div>
			<AbsoluteFill style={{background: 'white', opacity: flash}} />
		</Center>
	);
};

// 2. Easing curves drawn with dots riding them.
const Curves: React.FC<ReelProps> = ({accent}) => {
	const f = useCurrentFrame();
	const u = useU();
	const fns: [string, (t: number) => number][] = [
		['linear', (t) => t], ['ease-in', (t) => t * t * t], ['ease-out', (t) => 1 - (1 - t) ** 3],
		['ease-in-out', (t) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2)],
		['back', (t) => 1 + 2.7 * (t - 1) ** 3 + 1.7 * (t - 1) ** 2], ['expo', (t) => (t === 1 ? 1 : 1 - 2 ** (-10 * t))],
	];
	const draw = interpolate(f, [0, 25], [0, 1], {...clamp, easing: ease});
	const t = interpolate(f, [10, 45], [0, 1], clamp);
	return (
		<Center bg="#f4efe6">
			<div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 40 * u}}>
				{fns.map(([name, fn], i) => {
					const pts = Array.from({length: 41}, (_, k) => `${(k / 40) * 200},${200 - fn(k / 40) * 200}`).join(' ');
					return (
						<div key={i} style={{textAlign: 'center', fontFamily, color: '#222', fontSize: 30 * u}}>
							<svg width={240 * u} height={240 * u} viewBox="-20 -20 240 240">
								<polyline points={pts} fill="none" stroke="#222" strokeWidth={4} pathLength={1}
									strokeDasharray={1} strokeDashoffset={1 - draw} />
								<circle cx={t * 200} cy={200 - fn(t) * 200} r={10} fill={accent} />
							</svg>
							{name}
						</div>
					);
				})}
			</div>
		</Center>
	);
};

// 3. Circle -> triangle -> star -> square morph.
const Morph: React.FC<ReelProps> = () => {
	const f = useCurrentFrame();
	const u = useU();
	const shapes = [
		'M100,10 C150,10 190,50 190,100 C190,150 150,190 100,190 C50,190 10,150 10,100 C10,50 50,10 100,10 Z',
		'M100,15 C100,15 190,180 190,180 C190,180 10,180 10,180 C10,180 100,15 100,15 Z',
		'M100,10 C115,75 190,75 190,75 C130,115 155,190 155,190 C100,145 45,190 45,190 C70,115 10,75 10,75 C85,75 100,10 100,10 Z',
		'M20,20 C20,20 180,20 180,20 C180,20 180,180 180,180 C180,180 20,180 20,180 C20,180 20,20 20,20 Z',
	];
	const seg = 14;
	const i = Math.min(Math.floor(f / seg), shapes.length - 2);
	const p = interpolate(f - i * seg, [0, seg * 0.6], [0, 1], {...clamp, easing: ease});
	let d: string;
	try {
		d = interpolatePath(p, shapes[i], shapes[i + 1]);
	} catch {
		d = p < 0.5 ? shapes[i] : shapes[i + 1];
	}
	return (
		<Center bg="#2440ff">
			<svg width={600 * u} height={600 * u} viewBox="0 0 200 200"><path d={d} fill="white" /></svg>
		</Center>
	);
};

// 4. Black/white tiles with an accent wipe.
const Tiles: React.FC<ReelProps> = ({accent}) => {
	const f = useCurrentFrame();
	const {width, height} = useVideoConfig();
	const n = 8;
	const s = width / n;
	const wipe = interpolate(f, [8, 26], [-0.2, 1.2], clamp);
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{Array.from({length: n * Math.ceil(height / s)}).map((_, k) => {
				const x = k % n, y = Math.floor(k / n);
				const on = (x + y + Math.floor(f / 4)) % 2 === 0;
				return <div key={k} style={{position: 'absolute', left: x * s, top: y * s, width: s, height: s,
					background: (x / n) < wipe ? accent : on ? 'white' : 'black'}} />;
			})}
		</AbsoluteFill>
	);
};

// 5. Rotating 3D dot sphere.
const Sphere: React.FC<ReelProps> = ({accent}) => {
	const f = useCurrentFrame();
	const u = useU();
	const N = 420;
	const rot = f / 30;
	const dots = Array.from({length: N}, (_, i) => {
		const y = 1 - (i / (N - 1)) * 2;
		const r = Math.sqrt(1 - y * y);
		const th = i * 2.399963 + rot;
		return {x: Math.cos(th) * r, y, z: Math.sin(th) * r};
	});
	return (
		<Center bg="#050507">
			<svg width={760 * u} height={760 * u} viewBox="-1.2 -1.2 2.4 2.4">
				{dots.sort((a, b) => a.z - b.z).map((d, i) => (
					<circle key={i} cx={d.x} cy={d.y * 0.98} r={0.012 + 0.012 * (d.z + 1)} fill={d.z > 0 ? 'white' : accent}
						opacity={0.35 + 0.65 * (d.z + 1) / 2} />
				))}
			</svg>
		</Center>
	);
};

// 6. One word per beat with a motion-blurred slide (beat-relative frames passed in).
const Words: React.FC<ReelProps & {starts: number[]}> = ({words, accent, starts}) => {
	const f = useCurrentFrame();
	const u = useU();
	let i = 0;
	while (i + 1 < starts.length && f >= starts[i + 1]) i++;
	const local = f - starts[i];
	const p = interpolate(local, [0, 6], [0, 1], {...clamp, easing: ease});
	const colors = ['white', 'white', '#4f7bff', 'white', '#c6ff3d', 'white'];
	return (
		<Center bg={i % 2 ? '#0b0b0c' : '#141416'}>
			<div style={{fontFamily, fontWeight: 800, fontSize: 230 * u, color: colors[i % colors.length] || accent,
				transform: `translateX(${(1 - p) * 300 * u}px)`, filter: `blur(${(1 - p) * 18 * u}px)`}}>{words[i]}</div>
		</Center>
	);
};

// 7. Prompt bar typing + option pills with a sliding highlight.
const Prompt: React.FC<ReelProps> = ({prompt, options, accent}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const n = Math.floor(interpolate(f, [6, 6 + prompt.length * 1.2], [0, prompt.length], clamp));
	const enter = spring({frame: f, fps, config: {damping: 14}});
	const sel = Math.min(options.length - 1, Math.floor(interpolate(f, [30, 50], [0, options.length - 1], clamp) + 0.5));
	const slide = spring({frame: f - 30, fps, config: {damping: 16}}) * (options.length - 1);
	return (
		<Center bg="#0d0f14">
			<div style={{transform: `translateY(${(1 - enter) * 200 * u}px)`, opacity: enter, display: 'flex', flexDirection: 'column',
				alignItems: 'center', gap: 50 * u}}>
				<div style={{width: 900 * u, padding: `${34 * u}px ${44 * u}px`, borderRadius: 40 * u, background: '#1b1e26',
					border: `${2 * u}px solid #2c313d`, fontFamily, fontSize: 46 * u, color: 'white',
					boxShadow: `0 0 ${80 * u}px ${accent}33`}}>
					{prompt.slice(0, n)}<span style={{opacity: f % 16 < 8 ? 1 : 0}}>|</span>
				</div>
				<div style={{position: 'relative', display: 'flex', background: '#1b1e26', borderRadius: 999, padding: 8 * u}}>
					<div style={{position: 'absolute', top: 8 * u, left: 8 * u + slide * 240 * u, width: 240 * u, height: 90 * u,
						borderRadius: 999, background: accent}} />
					{options.map((o, i) => (
						<div key={i} style={{position: 'relative', width: 240 * u, height: 90 * u, display: 'flex', alignItems: 'center',
							justifyContent: 'center', fontFamily, fontWeight: 600, fontSize: 38 * u, color: i === sel ? '#0d0f14' : '#9aa3b5'}}>{o}</div>
					))}
				</div>
			</div>
		</Center>
	);
};

// 8. Logo drawn as a stroke, then filled, with the tagline.
const Logo: React.FC<ReelProps> = ({brand, tagline, accent}) => {
	const f = useCurrentFrame();
	const u = useU();
	const draw = interpolate(f, [0, 30], [0, 1], {...clamp, easing: ease});
	const fill = interpolate(f, [26, 40], [0, 1], clamp);
	return (
		<Center bg="#000">
			<svg width={900 * u} height={300 * u} viewBox="0 0 900 300">
				<text x="450" y="200" textAnchor="middle" fontFamily={fontFamily} fontWeight={800} fontSize={190}
					fill={`rgba(255,255,255,${fill})`} stroke={accent} strokeWidth={3} pathLength={1}
					strokeDasharray={2400} strokeDashoffset={2400 * (1 - draw)}>{brand}</text>
			</svg>
			<div style={{fontFamily, color: '#bbb', fontSize: 44 * u, opacity: fill, marginTop: -40 * u}}>{tagline}</div>
		</Center>
	);
};

const SCENES: [React.FC<any>, number][] = [
	// [component, number of beats it lasts]
	[Burst, 5], [Curves, 4], [Morph, 4], [Tiles, 3], [Sphere, 4], [Prompt, 4], [Words, 6], [Logo, 4],
];

export const reelBeatsUsed = SCENES.reduce((s, [, n]) => s + n, 0);

export const MotionReel: React.FC<ReelProps> = (props) => {
	const {fps} = useVideoConfig();
	const b = props.beats;
	let k = 0;
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{SCENES.map(([Scene, n], i) => {
				const from = i === 0 ? 0 : Math.round(b[k] * fps);
				const to = Math.round((b[k + n] ?? b[b.length - 1] + 1) * fps);
				const starts = Array.from({length: n}, (_, j) => Math.round(b[k + j] * fps) - from);
				k += n;
				return (
					<Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)}>
						<Scene {...props} starts={starts} />
					</Sequence>
				);
			})}
		</AbsoluteFill>
	);
};
