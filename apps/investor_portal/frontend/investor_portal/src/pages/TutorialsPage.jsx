import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, HelpCircle, Play, BookOpen, FileText, ArrowUpRight } from 'lucide-react';
import { TUTORIALS } from '../tutorialData.js';

const CATEGORY_INFO = {
  'all': { label: 'All Tutorials', icon: BookOpen },
  'getting-started': { label: 'Getting Started', icon: Play },
  'admin': { label: 'Admin Operations', icon: FileText },
  'launching': { label: 'Launching Apps', icon: ArrowUpRight },
};

const TutorialDetail = ({ tutorial, onBack }) => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="font-bold text-gray-900 dark:text-slate-100">{tutorial.title}</h1>
            <p className="text-xs text-gray-500 dark:text-slate-400">{tutorial.duration} min</p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {tutorial.videoUrl && (
          <div className="bg-black rounded-xl overflow-hidden mb-8 shadow-lg">
            <video
              controls
              preload="metadata"
              className="w-full"
              style={{ maxHeight: '480px' }}
            >
              <source src={tutorial.videoUrl} type="video/mp4" />
              Your browser does not support video playback.
            </video>
          </div>
        )}

        <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-2">About This Tutorial</h2>
          <p className="text-gray-600 dark:text-slate-400">{tutorial.description}</p>
        </div>

        {tutorial.guideUrl && (
          <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-slate-100">Step-by-Step Guide</h3>
                <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
                  View the screenshot guide with detailed instructions for each step.
                </p>
              </div>
              <a
                href={tutorial.guideUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium flex items-center gap-2"
              >
                <BookOpen className="w-4 h-4" />
                Open Guide
              </a>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

const TutorialsPage = ({ onBack }) => {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTutorial, setSelectedTutorial] = useState(null);

  const handleBack = onBack || (() => navigate('/dashboard'));

  if (selectedTutorial) {
    return <TutorialDetail tutorial={selectedTutorial} onBack={() => setSelectedTutorial(null)} />;
  }

  const filtered = selectedCategory === 'all'
    ? TUTORIALS
    : TUTORIALS.filter(t => t.category === selectedCategory);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <button
                onClick={handleBack}
                className="p-2 text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <HelpCircle className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h1 className="font-bold text-gray-900 dark:text-slate-100">Help & Tutorials</h1>
                <p className="text-xs text-gray-500 dark:text-slate-400">Learn how to use the platform</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-2 mb-8 flex-wrap">
          {Object.entries(CATEGORY_INFO).map(([key, { label }]) => (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                selectedCategory === key
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-slate-800 text-gray-600 dark:text-slate-300 border border-gray-200 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-700/50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(tutorial => (
            <button
              key={tutorial.id}
              onClick={() => setSelectedTutorial(tutorial)}
              className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 text-left hover:shadow-md hover:border-gray-200 dark:hover:border-slate-600 transition group"
            >
              <div className="bg-gray-100 dark:bg-slate-700 rounded-lg h-36 mb-4 flex items-center justify-center group-hover:bg-blue-50 dark:group-hover:bg-blue-900/30 transition">
                {tutorial.videoUrl ? (
                  <Play className="w-10 h-10 text-gray-300 dark:text-slate-500 group-hover:text-blue-400 transition" />
                ) : (
                  <BookOpen className="w-10 h-10 text-gray-300 dark:text-slate-500 group-hover:text-blue-400 transition" />
                )}
              </div>

              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition">
                  {tutorial.title}
                </h3>
                <span className="text-xs text-gray-400 dark:text-slate-500 whitespace-nowrap">{tutorial.duration}</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-slate-400 mt-1 line-clamp-2">{tutorial.description}</p>

              <div className="mt-3 flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  tutorial.category === 'getting-started' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' :
                  tutorial.category === 'admin' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' :
                  'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300'
                }`}>
                  {CATEGORY_INFO[tutorial.category]?.label || tutorial.category}
                </span>
                {tutorial.videoUrl && (
                  <span className="text-xs text-gray-400 dark:text-slate-500 flex items-center gap-1">
                    <Play className="w-3 h-3" /> Video
                  </span>
                )}
                {tutorial.guideUrl && (
                  <span className="text-xs text-gray-400 dark:text-slate-500 flex items-center gap-1">
                    <BookOpen className="w-3 h-3" /> Guide
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">
            <HelpCircle className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-slate-600" />
            <p>No tutorials in this category yet.</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default TutorialsPage;
