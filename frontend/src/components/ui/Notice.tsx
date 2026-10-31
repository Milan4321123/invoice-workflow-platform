import React from 'react';

/** Title plus an optional second line, for toast notifications */
export function Notice({ title, text }: { title: string; text?: string }) {
  return (
    <div>
      <p className="font-semibold">{title}</p>
      {text && <p className="mt-0.5 text-sm font-normal opacity-90">{text}</p>}
    </div>
  );
}
