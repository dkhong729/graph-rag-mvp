export type SseMessage = {
  event: string;
  data: any;
};

export async function consumeSse(
  stream: ReadableStream<Uint8Array>,
  onMessage: (message: SseMessage) => void
) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const chunk of parts) {
      const trimmed = chunk.trim();
      if (!trimmed) continue;
      let event = "message";
      const dataLines: string[] = [];
      for (const line of trimmed.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      const dataText = dataLines.join("\n");
      let data: any = dataText;
      try {
        data = JSON.parse(dataText);
      } catch {
        // keep raw string
      }
      onMessage({ event, data });
    }
  }
}
