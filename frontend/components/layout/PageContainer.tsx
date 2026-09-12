import { ReactNode } from "react";

interface PageContainerProps {
    children: ReactNode;
}

export default function PageContainer({
                                          children,
                                      }: PageContainerProps) {
    return (
        <main className="min-h-[calc(100vh-80px)] bg-[#f7f8fa] px-8 py-7">
            <div className="mx-auto max-w-[1600px]">
                {children}
            </div>
        </main>
    );
}