import {Composition} from 'remotion';
import {GlowPromo, promoDuration, PromoProps} from './GlowPromo';
import {MotionReel, reelBeatsUsed, reelDefaults} from './MotionReel';

// Defaults are a neutral demo brand. Pass real values with --props='{"brand":"..."}'.
const defaults: PromoProps = {
	brand: 'Nova',
	accent: '#1ED760',
	headline: ['Listen', 'to', 'your', 'favourite', 'artists'],
	accentWord: 'artists',
	subline: 'with a single click',
	cards: [
		{title: 'Late Night Drive', meta: 'Playlist · 42 songs'},
		{title: 'Chill Mornings', meta: 'Playlist · 28 songs'},
		{title: 'Gym Hits 2026', meta: 'Playlist · 60 songs'},
		{title: 'Focus Flow', meta: 'Playlist · 35 songs'},
	],
	cta: 'Download now',
};

export const RemotionRoot: React.FC = () => {
	return (
		<>
			<Composition
				id="GlowPromo"
				component={GlowPromo}
				durationInFrames={promoDuration}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={defaults}
			/>
			<Composition
				id="GlowPromoWide"
				component={GlowPromo}
				durationInFrames={promoDuration}
				fps={30}
				width={1920}
				height={1080}
				defaultProps={defaults}
			/>
			<Composition
				id="MotionReel"
				component={MotionReel}
				durationInFrames={Math.ceil((reelDefaults.beats[reelBeatsUsed] ?? 18) * 60)}
				fps={60}
				width={1920}
				height={1080}
				defaultProps={reelDefaults}
			/>
			<Composition
				id="MotionReelVertical"
				component={MotionReel}
				durationInFrames={Math.ceil((reelDefaults.beats[reelBeatsUsed] ?? 18) * 60)}
				fps={60}
				width={1080}
				height={1920}
				defaultProps={reelDefaults}
			/>
		</>
	);
};
