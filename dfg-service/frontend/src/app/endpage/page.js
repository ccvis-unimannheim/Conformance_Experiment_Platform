import ExpNavigation from "../../components/General/ExpNavigation";

// The DFG study's own end page. It deliberately makes no API calls: the main
// app's /endpage marks the visitor's ProVi assignment complete and stores
// feedback against the ProVi user, which must never happen for a DFG run.
export default function EndPage() {
  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <ExpNavigation />
      <main className="flex items-center justify-center flex-grow p-8">
        <section className="max-w-2xl p-12 text-center bg-white rounded-md shadow-md">
          <h1 className="mb-6 text-2xl font-bold">Thank you for participating!</h1>
          <p className="text-lg leading-relaxed">
            Your answers have been saved. You can now close this window.
          </p>
        </section>
      </main>
    </div>
  );
}
