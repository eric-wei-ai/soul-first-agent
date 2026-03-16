# DingTalk Setup Example

Step-by-step guide for deploying an AI employee via DingTalk Stream Mode.

## Prerequisites
- macOS or Linux
- Node.js 22+
- OpenClaw installed
- DingTalk developer account

## Steps
1. Install OpenClaw: `npm install -g openclaw@latest`
2. Run onboard: `openclaw onboard`
3. Install DingTalk plugin: `openclaw plugins install @openclaw-china/channels`
4. Configure credentials: `openclaw config set channels.dingtalk.clientId "your_id"`
5. Start gateway: `openclaw gateway`

See the [full DingTalk guide](https://github.com/openclaw/openclaw/pull/47944) for details.
