export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50/50 relative overflow-hidden">
            {/* Background elements */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
                <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-[#6d5dfc]/10 blur-3xl" />
                <div className="absolute top-1/2 -left-20 h-64 w-64 rounded-full bg-[#6d5dfc]/5 blur-3xl" />
            </div>

            <div className="relative z-10 w-full max-w-md p-6">
                {children}
            </div>
        </div>
    );
}
