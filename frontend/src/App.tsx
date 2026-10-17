/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Banner } from './components/Banner';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { OverviewPage } from './pages/OverviewPage';
import { UploadPage } from './pages/UploadPage';
import { QueuePage } from './pages/QueuePage';
import { MachinePage } from './pages/MachinePage';
import { HistoryPage } from './pages/HistoryPage';
import { StatusPage } from './pages/StatusPage';
import { NotFoundPage } from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0b0f17] text-zinc-100 flex flex-col selection:bg-amber-500 selection:text-black antialiased">
        {/* Yellow banner on every page */}
        <Banner />

        {/* Global Navigation Header with 6 menu links */}
        <Navbar />

        {/* Main Content Area */}
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/machines/:id" element={<MachinePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>

        {/* Standard Industrial Footer */}
        <Footer />
      </div>
    </BrowserRouter>
  );
}
