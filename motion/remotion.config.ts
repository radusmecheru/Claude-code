import {Config} from '@remotion/cli/config';
import {existsSync} from 'fs';

// Cloud sessions ship Playwright's headless shell; use it instead of downloading one.
const shell = process.env.REMOTION_BROWSER ?? '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
if (existsSync(shell)) {
	Config.setBrowserExecutable(shell);
}
Config.setConcurrency(4);
Config.setCrf(18);
