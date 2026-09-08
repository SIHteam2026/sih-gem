"use client";

import React from "react";
import Navbar from "@/components/Navbar";

export interface HomeShellProps {
  header?: React.ReactNode;
  heroSlot?: React.ReactNode;
  livingVisualSlot?: React.ReactNode;
  contextSlot?: React.ReactNode;
  recentProcurementSlot?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export default function HomeShell({
  header = <Navbar />,
  heroSlot,
  livingVisualSlot,
  contextSlot,
  recentProcurementSlot,
  children,
  className = "",
}: HomeShellProps) {
 return (
 <div className={"min-h-screen bg-white text-[#111827] flex flex-col selection:bg-[#d8e6ee] overflow-x-hidden">
 {header}
 <main id=main-content className=mx-auto w-full max-w-[1360px] flex-1 px-6 sm:px-10 lg:px-12 pt-6 sm:pt-8 lg:pt-10 pb-12>
 {(heroSlot || contextSlot) && (
 <section className=grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-6 xl:gap-10 lg:items-start>
 {heroSlot && (
 <div className=lg:col-span-7 xl:col-span-7 flex flex-col justify-start>
 {heroSlot}
 </div>
 )}
 {livingVisualSlot && (
 <div className=hidden lg:flex lg:col-span-1 justify-center items-center self-stretch pt-6>
 {livingVisualSlot}
 </div>
 )}
 {contextSlot && (
 <div className={w-full flex flex-col justify-start items-end }>
 {contextSlot}
 </div>
 )}
 </section>
 )}
 {recentProcurementSlot && (
 <section className=mt-8>
 {recentProcurementSlot}
 </section>
 )}
 {children}
 </main>
 </div>
 );
}
