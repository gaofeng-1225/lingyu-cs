/**
 * RTC 二进制消息 TLV 编解码
 * 协议：type(4字节 ASCII) + length(4字节大端) + value(JSON 文本)
 */

export function string2tlv(str: string, type: string): ArrayBuffer {
  const typeBuffer = new Uint8Array(4);
  for (let i = 0; i < Math.min(type.length, 4); i++) {
    typeBuffer[i] = type.charCodeAt(i);
  }

  const valueBytes = new TextEncoder().encode(str);
  const length = valueBytes.length;

  const tlv = new Uint8Array(8 + length);
  tlv.set(typeBuffer, 0);
  tlv[4] = (length >> 24) & 0xff;
  tlv[5] = (length >> 16) & 0xff;
  tlv[6] = (length >> 8) & 0xff;
  tlv[7] = length & 0xff;
  tlv.set(valueBytes, 8);
  return tlv.buffer;
}

export function tlv2String(buffer: ArrayBuffer): { type: string; value: string } {
  const view = new Uint8Array(buffer);
  let type = '';
  for (let i = 0; i < 4; i++) {
    type += String.fromCharCode(view[i]);
  }
  const length =
    (view[4] << 24) | (view[5] << 16) | (view[6] << 8) | view[7];
  const value = new TextDecoder().decode(view.subarray(8, 8 + length));
  return { type, value };
}
