"use client"

import { FOOD_TYPES } from "@/lib/production/constants"

const selectClassName =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

export function FoodTypeSelect({ id, value, onChange, required = true }) {
  return (
    <select
      id={id}
      className={selectClassName}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required={required}
    >
      {FOOD_TYPES.map(({ value: v, label }) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  )
}
