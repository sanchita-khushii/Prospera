import React from "react";

export function Input({ className, ...props }) {
  return <input className={`${className} px-4 py-2 rounded-lg`} {...props} />;
}
