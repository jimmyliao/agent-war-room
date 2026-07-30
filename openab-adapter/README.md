# OpenAB Adapter

The COSCUP demo uses the existing OpenAB OSS deployment as the Discord/ACP
broker. This directory will contain a case-specific `warroom-acp` process that:

1. Accepts ACP messages from OpenAB.
2. Maps the Discord thread identity to a GEAP session.
3. Calls the remote ADK War Room.
4. Projects allowlisted public events back to Discord.

OpenAB itself is not copied or modified in this repository.

