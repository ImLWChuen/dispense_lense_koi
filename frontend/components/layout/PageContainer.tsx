import { ReactNode } from "react";

interface PageContainerProps {
    children: ReactNode;
}

export default function PageContainer({
    children,
}: PageContainerProps) {
    return (
        <main className="min-h-[calc(100vh-80px)] bg-[#f7f8fa] dark:bg-[#0b0f19] text-gray-900 dark:text-gray-100 px-4 sm:px-6 lg:px-8 py-6 sm:py-7 transition-colors duration-200">
            <div className="mx-auto max-w-[1600px]">
                {children}
            </div>
        </main>
    );
}