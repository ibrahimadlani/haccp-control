import { Geist } from "next/font/google"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { OperatorProvider } from "@/lib/contexts/OperatorContext"
import { PlatformProvider } from "@/lib/contexts/PlatformContext"
import "./globals.css"

const geist = Geist({ subsets: ["latin"] })

export const metadata = {
  title: "HACCP Control",
  description: "Traçabilité sanitaire HACCP",
}

export default function RootLayout({ children }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={geist.className}>
        <TooltipProvider>
          <PlatformProvider>
            <OperatorProvider>
              {children}
              <Toaster richColors position="top-right" />
            </OperatorProvider>
          </PlatformProvider>
        </TooltipProvider>
      </body>
    </html>
  )
}
