from pagermaid.enums import Message
from pagermaid.listener import listener
from pagermaid.utils import execute
import os
import re
import platform
import urllib.request

NEXTTRACE_PATH = "/var/lib/pagermaid/plugins/nexttrace"

@listener(
    is_plugin=False,
    command="t",
    need_admin=True,
    description="Perform a network trace using nexttrace.",
    parameters="Provide the target IP or domain."
)
async def trace(message: Message):

    def extract_ip(text):
        ip_pattern = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
        match = ip_pattern.search(text)
        return match.group(0) if match else None

    def detect_architecture():
        arch = platform.machine().lower()

        if arch in ["x86_64", "amd64"]:
            url = "https://github.com/nxtrace/NTrace-core/releases/latest/download/nexttrace_linux_amd64"
        elif arch in ["aarch64", "arm64"]:
            url = "https://github.com/nxtrace/NTrace-core/releases/latest/download/nexttrace_linux_arm64"
        else:
            raise Exception(f"Unsupported architecture: {arch}")

        if not os.path.exists(NEXTTRACE_PATH):
            try:
                urllib.request.urlretrieve(url, NEXTTRACE_PATH)
                os.chmod(NEXTTRACE_PATH, 0o755)
            except Exception as e:
                raise Exception(f"Error downloading nexttrace: {str(e)}")

    try:
        detect_architecture()
    except Exception as e:
        await message.edit(f"Error: {str(e)}")
        return

    target = message.arguments

    if not target and message.reply_to_message:
        target = extract_ip(message.reply_to_message.text or "")

    if not target:
        await message.edit("Error: No target specified or no IP found in the replied message.")
        return

    command = f"env NEXTTRACE_NO_COLOR=1 {NEXTTRACE_PATH} -q 1 {target}"

    try:
        result = await execute(command)
    except Exception as e:
        await message.edit(f"Error executing command: {str(e)}")
        return

    if result:
        result = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', result)
        result = re.sub(r'\[\d{1,2}(;\d{1,2})*m', '', result)

        result_lines = result.splitlines()
        result_lines = [line for line in result_lines if line.strip()]
        result = "\n".join(result_lines)

        title = f"**Traceroute to {target}**"
        final_result = f"{title}\n```text\n{result}\n```"
        
        if len(final_result) > 4000:
            final_result = final_result[:4000] + "\n...```"
            
        await message.edit(final_result)
    else:
        await message.edit("No result returned. The target might have ICMP disabled or is unreachable.")
