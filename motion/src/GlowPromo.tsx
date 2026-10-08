import React from 'react';
import {
	AbsoluteFill,
	Easing,
	interpolate,
	Sequence,
	spring,
	useCurrentFrame,
	staticFile,
	useVideoConfig,
} from 'remotion';
import {loadFont} from '@remotion/fonts';

// Fonts ship in public/fonts so renders work offline (the render browser skips the network proxy).
const fontFamily = 'Inter';
for (const weight of ['400', '600', '800']) {
	loadFont({family: fontFamily, url: staticFile(`fonts/Inter-${weight}.ttf`), weight});
}

export type PromoProps = {
	brand: string;
	accent: string;
	headline: string[];
	accentWord: string;
	subline: string;
	cards: {title: string; meta: string}[];
	cta: string;
};

// Scene timeline in frames at 30fps. Each scene fades over FADE frames at its edges.
const SCENES = {
	intro: [0, 75],
	phone: [70, 110],
	cards: [175, 120],
	words: [290, 100],
	streak: [385, 35],
	outro: [415, 65],
} as const;
const FADE = 8;
export const promoDuration = 480;

const ease = Easing.bezier(0.16, 1, 0.3, 1);

// Size unit: 1 = 1px on a 1080-wide short side, so layouts work in 9:16 and 16:9.
const useU = () => {
	const {width, height} = useVideoConfig();
	return Math.min(width, height) / 1080;
};

const SceneFade: React.FC<{len: number; children: React.ReactNode}> = ({len, children}) => {
	const f = useCurrentFrame();
	const o = interpolate(f, [0, FADE, len - FADE, len], [0, 1, 1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

// The signature look: near-black background with a breathing radial glow in the accent colour.
const Glow: React.FC<{accent: string; x?: number; y?: number; size?: number; strength?: number}> = ({
	accent,
	x = 50,
	y = 55,
	size = 60,
	strength = 1,
}) => {
	const f = useCurrentFrame();
	const breathe = 1 + Math.sin(f / 18) * 0.06;
	return (
		<AbsoluteFill
			style={{
				background: `radial-gradient(circle at ${x}% ${y}%, ${accent}${alpha(0.55 * strength)} 0%, ${accent}${alpha(
					0.18 * strength,
				)} ${size * 0.45 * breathe}%, transparent ${size * breathe}%)`,
				filter: 'blur(20px)',
			}}
		/>
	);
};

const alpha = (a: number) =>
	Math.round(Math.max(0, Math.min(1, a)) * 255)
		.toString(16)
		.padStart(2, '0');

const Logo: React.FC<{accent: string; size: number}> = ({accent, size}) => (
	<svg width={size} height={size} viewBox="0 0 100 100">
		<rect x="2" y="2" width="96" height="96" rx="28" fill={accent} />
		<path d="M50 18 C53 40 60 47 82 50 C60 53 53 60 50 82 C47 60 40 53 18 50 C40 47 47 40 50 18 Z" fill="#0b0b0b" />
	</svg>
);

const Intro: React.FC<PromoProps> = ({brand, accent}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const dot = spring({frame: f - 6, fps, config: {damping: 12, stiffness: 120}});
	const word = interpolate(f, [26, 46], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
	const glowGrow = interpolate(f, [0, 40], [0.2, 1], {extrapolateRight: 'clamp', easing: ease});
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<Glow accent={accent} size={70 * glowGrow} strength={glowGrow} />
			<div style={{display: 'flex', alignItems: 'center', gap: 28 * u}}>
				<div style={{transform: `scale(${dot}) rotate(${(1 - dot) * -90}deg)`}}>
					<Logo accent={accent} size={150 * u} />
				</div>
				<div
					style={{
						fontFamily,
						fontWeight: 800,
						fontSize: 120 * u,
						color: 'white',
						letterSpacing: -4 * u,
						opacity: word,
						filter: `blur(${(1 - word) * 18 * u}px)`,
						transform: `translateX(${(1 - word) * -40 * u}px)`,
						maxWidth: word * 900 * u,
						overflow: 'hidden',
						whiteSpace: 'nowrap',
					}}
				>
					{brand}
				</div>
			</div>
		</AbsoluteFill>
	);
};

const AppIcon: React.FC<{i: number; accent: string; on: number}> = ({i, accent, on}) => {
	const hues = [accent, '#ff5a5f', '#7c5cff', '#ffb020', '#2ec5ff', '#ff4fd8'];
	const c = hues[i % hues.length];
	return (
		<div
			style={{
				aspectRatio: '1',
				borderRadius: '24%',
				background: `linear-gradient(135deg, ${c}, ${c}88)`,
				opacity: on,
				transform: `scale(${0.6 + on * 0.4})`,
				boxShadow: `0 0 ${on * 18}px ${c}66`,
			}}
		/>
	);
};

const Phone: React.FC<PromoProps> = ({accent}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const enter = spring({frame: f, fps, config: {damping: 16, stiffness: 70}});
	const rotY = interpolate(enter, [0, 1], [70, -14]) + Math.sin(f / 25) * 4;
	const rotX = interpolate(enter, [0, 1], [25, 8]);
	const w = 420 * u;
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', perspective: 1800 * u}}>
			<Glow accent={accent} size={55} />
			<div
				style={{
					width: w,
					height: w * 2.08,
					borderRadius: 64 * u,
					background: '#050505',
					border: `${10 * u}px solid #1c1c1e`,
					boxShadow: `0 ${40 * u}px ${120 * u}px #000, 0 0 ${80 * u}px ${accent}55, inset 0 0 0 ${2 * u}px #3a3a3c`,
					transform: `translateY(${(1 - enter) * 400 * u}px) rotateY(${rotY}deg) rotateX(${rotX}deg)`,
					padding: 34 * u,
					display: 'grid',
					gridTemplateColumns: 'repeat(4, 1fr)',
					gridAutoRows: 'min-content',
					gap: 22 * u,
					paddingTop: 110 * u,
					overflow: 'hidden',
					position: 'relative',
				}}
			>
				<div
					style={{
						position: 'absolute',
						top: 22 * u,
						left: '50%',
						width: 120 * u,
						height: 34 * u,
						marginLeft: -60 * u,
						borderRadius: 20 * u,
						background: '#000',
					}}
				/>
				{Array.from({length: 20}).map((_, i) => (
					<AppIcon
						key={i}
						i={i}
						accent={accent}
						on={interpolate(f, [20 + i * 2, 30 + i * 2], [0, 1], {
							extrapolateLeft: 'clamp',
							extrapolateRight: 'clamp',
						})}
					/>
				))}
				{/* Glass reflection sweeping across the screen. */}
				<div
					style={{
						position: 'absolute',
						inset: 0,
						background: `linear-gradient(115deg, transparent ${interpolate(f, [0, 110], [-40, 90])}%, #ffffff22 ${
							interpolate(f, [0, 110], [-40, 90]) + 8
						}%, transparent ${interpolate(f, [0, 110], [-40, 90]) + 16}%)`,
					}}
				/>
			</div>
		</AbsoluteFill>
	);
};

const Cards: React.FC<PromoProps> = ({accent, cards}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const dolly = interpolate(f, [0, 120], [1, 1.1]);
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', perspective: 2000 * u}}>
			<Glow accent={accent} x={45} y={50} size={60} />
			<div
				style={{
					display: 'flex',
					flexDirection: 'column',
					gap: 26 * u,
					transform: `scale(${dolly}) rotateX(12deg) rotateY(-10deg)`,
				}}
			>
				{cards.map((c, i) => {
					const s = spring({frame: f - 6 - i * 7, fps, config: {damping: 18, stiffness: 110}});
					const active = i === 1 && f > 55;
					return (
						<div
							key={i}
							style={{
								width: 760 * u,
								display: 'flex',
								alignItems: 'center',
								gap: 28 * u,
								padding: 24 * u,
								borderRadius: 28 * u,
								background: active ? `${accent}26` : '#ffffff10',
								border: `${2 * u}px solid ${active ? accent : '#ffffff1f'}`,
								backdropFilter: 'blur(10px)',
								opacity: s,
								filter: `blur(${(1 - s) * 14 * u}px)`,
								transform: `translateX(${(1 - s) * 160 * u}px) scale(${active ? 1.04 : 1})`,
								boxShadow: active ? `0 0 ${60 * u}px ${accent}55` : 'none',
							}}
						>
							<div
								style={{
									width: 110 * u,
									height: 110 * u,
									borderRadius: 18 * u,
									background: `linear-gradient(135deg, ${['#ff7a18', '#7c5cff', '#ff4fd8', '#2ec5ff'][i % 4]}, #111)`,
								}}
							/>
							<div style={{fontFamily, flex: 1}}>
								<div style={{color: 'white', fontWeight: 600, fontSize: 44 * u}}>{c.title}</div>
								<div style={{color: '#ffffff88', fontSize: 30 * u, marginTop: 6 * u}}>{c.meta}</div>
							</div>
							<div
								style={{
									width: 76 * u,
									height: 76 * u,
									borderRadius: '50%',
									background: accent,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
								}}
							>
								<div
									style={{
										width: 0,
										height: 0,
										marginLeft: 6 * u,
										borderTop: `${16 * u}px solid transparent`,
										borderBottom: `${16 * u}px solid transparent`,
										borderLeft: `${26 * u}px solid #0b0b0b`,
									}}
								/>
							</div>
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

// Kinetic typography: each word blurs in on its own beat; the accent word glows.
const Words: React.FC<PromoProps> = ({accent, headline, accentWord, subline}) => {
	const f = useCurrentFrame();
	const u = useU();
	const sub = interpolate(f, [55, 70], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 80 * u}}>
			<Glow accent={accent} size={55} y={50} />
			<div
				style={{
					fontFamily,
					fontWeight: 800,
					fontSize: 104 * u,
					lineHeight: 1.05,
					letterSpacing: -3 * u,
					textAlign: 'center',
					display: 'flex',
					flexWrap: 'wrap',
					justifyContent: 'center',
					gap: `0 ${26 * u}px`,
					maxWidth: 900 * u,
				}}
			>
				{headline.map((w, i) => {
					const p = interpolate(f, [i * 6, i * 6 + 12], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
						easing: ease,
					});
					const isAccent = w === accentWord;
					return (
						<span
							key={i}
							style={{
								color: isAccent ? accent : 'white',
								opacity: p,
								filter: `blur(${(1 - p) * 16 * u}px)`,
								transform: `translateY(${(1 - p) * 50 * u}px)`,
								display: 'inline-block',
								textShadow: isAccent ? `0 0 ${40 * u}px ${accent}aa` : 'none',
							}}
						>
							{w}
						</span>
					);
				})}
			</div>
			<div
				style={{
					fontFamily,
					fontWeight: 400,
					fontSize: 52 * u,
					color: '#ffffffb0',
					marginTop: 40 * u,
					opacity: sub,
					filter: `blur(${(1 - sub) * 10 * u}px)`,
				}}
			>
				{subline}
			</div>
		</AbsoluteFill>
	);
};

// A bright horizontal light streak used as a transition beat.
const Streak: React.FC<PromoProps> = ({accent}) => {
	const f = useCurrentFrame();
	const u = useU();
	const grow = interpolate(f, [0, 14], [0, 1], {extrapolateRight: 'clamp', easing: ease});
	const thin = interpolate(f, [14, 34], [1, 0.05], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<div
				style={{
					width: `${grow * 90}%`,
					height: 16 * u * thin,
					borderRadius: 999,
					background: `linear-gradient(90deg, transparent, ${accent}, white, ${accent}, transparent)`,
					boxShadow: `0 0 ${60 * u}px ${accent}, 0 0 ${140 * u}px ${accent}`,
				}}
			/>
		</AbsoluteFill>
	);
};

const Outro: React.FC<PromoProps> = ({brand, accent, cta}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = useU();
	const s = spring({frame: f, fps, config: {damping: 14}});
	const pill = spring({frame: f - 16, fps, config: {damping: 14}});
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
			<Glow accent={accent} size={65} strength={1.2} />
			<div style={{display: 'flex', alignItems: 'center', gap: 24 * u, transform: `scale(${0.7 + s * 0.3})`, opacity: s}}>
				<Logo accent={accent} size={120 * u} />
				<div style={{fontFamily, fontWeight: 800, fontSize: 100 * u, color: 'white', letterSpacing: -3 * u}}>{brand}</div>
			</div>
			<div
				style={{
					marginTop: 50 * u,
					fontFamily,
					fontWeight: 600,
					fontSize: 40 * u,
					color: '#0b0b0b',
					background: accent,
					padding: `${18 * u}px ${44 * u}px`,
					borderRadius: 999,
					opacity: pill,
					transform: `translateY(${(1 - pill) * 30 * u}px)`,
					boxShadow: `0 0 ${50 * u}px ${accent}88`,
				}}
			>
				{cta}
			</div>
		</AbsoluteFill>
	);
};

export const GlowPromo: React.FC<PromoProps> = (props) => {
	const scenes: [keyof typeof SCENES, React.FC<PromoProps>][] = [
		['intro', Intro],
		['phone', Phone],
		['cards', Cards],
		['words', Words],
		['streak', Streak],
		['outro', Outro],
	];
	return (
		<AbsoluteFill style={{background: '#050806'}}>
			{scenes.map(([key, Scene]) => {
				const [from, len] = SCENES[key];
				return (
					<Sequence key={key} from={from} durationInFrames={len}>
						<SceneFade len={len}>
							<Scene {...props} />
						</SceneFade>
					</Sequence>
				);
			})}
		</AbsoluteFill>
	);
};
