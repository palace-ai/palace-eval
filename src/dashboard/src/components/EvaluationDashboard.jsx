import React, { useState, useMemo, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  ResponsiveContainer, ScatterChart, Scatter, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, LabelList, Cell
} from 'recharts';
import { 
  Upload, Filter, TrendingUp, Clock, CheckCircle, XCircle, 
  HelpCircle, BarChart2, List, AlertCircle, RadarIcon, Scale, Flame, Bot
} from 'lucide-react';
import { scaleOrdinal } from 'd3-scale';
import { schemeTableau10 } from 'd3-scale-chromatic';


const EvaluationDashboard = () => {
    const [data, setData] = useState([]);
    const [selectedFile, setSelectedFile] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [filters, setFilters] = useState({
        model: ['all'],
        paradigm: ['all'],
        environment: ['all'],
        tasklist: ['all']
    });
    const [currentPage, setCurrentPage] = useState(1);
    const [questionsPerPage] = useState(15);

    useEffect(() => {
        setCurrentPage(1);
    }, [filters]);

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        
        setLoading(true);
        setError('');
        
        try {
            const text = await file.text();
            const lines = text.split('\n').filter(line => line.trim());

            const isValid = lines.every(line => {
                try {
                const parsed = JSON.parse(line);
                return parsed.model && typeof parsed.accuracy === 'number';
                } catch {
                return false;
                }
            });
            if (!isValid) throw new Error('Invalid JSONL structure');
            
            const jsonlData = lines.map(line => {
                const parsed = JSON.parse(line);
                
                if (!parsed.model || !parsed.accuracy === undefined) {
                    throw new Error('Invalid JSONL format: Missing required fields');
                }
                
                return {
                    ...parsed,
                    detailed_report: parsed.detailed_report || {}
                };
            });
            
            setData(jsonlData);
            setSelectedFile(file.name);
        } catch (error) {
            setError('Error parsing JSONL file: ' + error.message);
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const getUniqueValues = (field) => {
        return [...new Set(data.map(item => item[field]))].sort();
    };

    const filteredData = useMemo(() => {
        return data.filter(item => {
            return (filters.model.includes('all' ) || filters.model.includes(item.model) ) &&
                   (filters.paradigm.includes('all' ) || filters.paradigm.includes(item.paradigm) ) &&
                   (filters.environment.includes('all' )  || filters.environment.includes(item.environment)) &&
                   (filters.tasklist.includes('all' )  || filters.tasklist.includes(item.tasklist));
        });
    }, [data, filters]);

    const agentComparison = useMemo(() => {
        const grouped = {};
        filteredData.forEach(item => {
            const agentName = item.agent || `${item.model} x ${item.paradigm}`;
            if (!grouped[agentName]) {
                grouped[agentName] = { 
                    name: agentName,
                    agent: agentName,
                    model: item.model,
                    paradigm: item.paradigm,
                    accuracy: [], 
                    total_time: [],
                    tasklists: new Set()
                };
            }
            grouped[agentName].accuracy.push(item.accuracy);
            grouped[agentName].total_time.push(item.total_time);
            grouped[agentName].tasklists.add(item.tasklist);
        });

        return Object.values(grouped).map(group => ({
            name: group.name,
            agent: group.agent,
            model: group.model,
            paradigm: group.paradigm,
            avg_accuracy: group.accuracy.reduce((a, b) => a + b, 0) / group.accuracy.length,
            avg_time: group.total_time.reduce((a, b) => a + b, 0) / group.total_time.length,
            num_tasks: group.tasklists.size
        })).sort((a, b) => b.avg_accuracy - a.avg_accuracy);
    }, [filteredData]);

    const taskDifficulty = useMemo(() => {
        const grouped = {};
        filteredData.forEach(item => {
            if (!grouped[item.tasklist]) {
                grouped[item.tasklist] = { 
                    name: item.tasklist, 
                    accuracies: [], 
                    times: [] 
                };
            }
            grouped[item.tasklist].accuracies.push(item.accuracy);
            grouped[item.tasklist].times.push(item.total_time);
        });

        return Object.values(grouped).map(group => ({
            name: group.name,
            avg_accuracy: group.accuracies.reduce((a, b) => a + b, 0) / group.accuracies.length,
            avg_time: group.times.reduce((a, b) => a + b, 0) / group.times.length,
            difficulty: 1 - (group.accuracies.reduce((a, b) => a + b, 0) / group.accuracies.length)
        })).sort((a, b) => b.difficulty - a.difficulty);
    }, [filteredData]);

    const accuracyTimeScatter = useMemo(() => {
        return   Object.values(
                filteredData.map((item, idx) => ({
            x: item.accuracy,
            y: item.total_time,
            name: `${item.agent || `${item.model} x ${item.paradigm}`} (${item.tasklist})`,
            agent: item.agent || `${item.model} x ${item.paradigm}`,
            tasklist: item.tasklist
                        })).reduce((acc, item) => {
                if (!acc[item.agent]) {
                acc[item.agent] = { agent: item.agent, sumX: 0, sumY: 0, count: 0, name: item.name, tasklist: item.tasklist};
                }
                acc[item.agent].sumX += item.x;
                acc[item.agent].sumY += item.y;
                acc[item.agent].count += 1;
                return acc;
                }, {})
                ).map(({ agent, sumX, sumY, count, name, tasklist}) => ({
                x: sumX / count,
                y: sumY / count,
                name: name,
                agent: agent,
                tasklist: tasklist, 
                accuracy: sumX / count, 
                time: sumY / count
                }));
    }, [filteredData]);

    const accuracyStepsScatter = useMemo(() => {
        return   Object.values(
                filteredData.map((item, idx) => ({
            x: item.accuracy,
            y: Object.values(item["detailed_report"])
                        .reduce( (acc, it)=> { 
                                 if(Object.hasOwn(it, "n_steps")){
                                  acc.total+=it["n_steps"]; acc.count+=1; 
                                 }
                                 return acc;
                                } ,
                                {
                                total:0.0,
                                count:0, 
                                average: function(){ 
                                        if(this.count==0) {return 0.0}
                                        else {return this.total/this.count}}
                                }
                        )
                        .average(),
            name: `${item.agent || `${item.model} x ${item.paradigm}`} (${item.tasklist})`,
            agent: item.agent || `${item.model} x ${item.paradigm}`,
            tasklist: item.tasklist
                        }))
            .reduce((acc, item) => {
                if (!acc[item.agent]) {
                acc[item.agent] = { agent: item.agent, sumX: 0, sumY: 0, count: 0, name: item.name, tasklist: item.tasklist};
                }
                acc[item.agent].sumX += item.x;
                acc[item.agent].sumY += item.y;
                acc[item.agent].count += 1;
                return acc;
                }, {})
         ).map(({ agent, sumX, sumY, count, name, tasklist}) => ({
                x: sumX / count,
                y: sumY / count,
                name: name,
                agent: agent,
                tasklist: tasklist, 
                accuracy: sumX / count, 
                n_steps: sumY / count
                })
        );
    }, [filteredData]);

    const modelTaskRadarData = useMemo(() => {
        const models = [...new Set(data.map(item => item.model))];
        const tasklists = [...new Set(data.map(item => item.tasklist))];
        
        return models.map(model => {
            const modelData = data.filter(item => item.model === model);
            const taskPerformances = {};
            
            tasklists.forEach(tasklist => {
                const taskData = modelData.filter(item => item.tasklist === tasklist);
                if (taskData.length > 0) {
                    taskPerformances[tasklist] = taskData.reduce((sum, item) => sum + item.accuracy, 0) / taskData.length;
                } else {
                    taskPerformances[tasklist] = 0;
                }
            });
            
            return {
                model,
                ...taskPerformances
            };
        });
    }, [data]);

    const agentPerformanceDetails = useMemo(() => {
        return filteredData
            .map(item => ({
                agent: item.agent || `${item.model} x ${item.paradigm}`,
                model: item.model,
                paradigm: item.paradigm,
                environment: item.environment,
                tasklist: item.tasklist,
                accuracy: item.accuracy,
                total_time: item.total_time
            }))
            .sort((a, b) => b.accuracy - a.accuracy);
    }, [filteredData]);

    const questionStats = useMemo(() => {
        if (!filteredData.length) return [];
        
        const stats = {};
        filteredData.forEach(run => {
            Object.entries(run.detailed_report).forEach(([question, details]) => {
                if (!stats[question]) {
                    stats[question] = {
                        question,
                        totalRuns: 0,
                        correctCount: 0,
                        avgTime: 0
                    };
                }
                
                stats[question].totalRuns++;
                stats[question].correctCount += details.is_correct ? 1 : 0;
                stats[question].avgTime += details.elapsed_time;
            });
        });
        
        return Object.values(stats).map(stat => ({
            ...stat,
            accuracy: stat.correctCount / stat.totalRuns,
            avgTime: stat.avgTime / stat.totalRuns,
            difficulty: 1 - (stat.correctCount / stat.totalRuns)
        })).sort((a, b) => b.difficulty - a.difficulty);
    }, [filteredData]);

    const radarData = useMemo(() => {
        const models = [...new Set(data.map(item => item.model))];
        return models.map(model => {
            const modelData = data.filter(item => item.model === model);
            const totalQuestions = modelData.reduce((sum, item) => sum + Object.keys(item.detailed_report).length, 0);
            const correctAnswers = modelData.reduce((sum, item) => {
                return sum + Object.values(item.detailed_report).filter(q => q.is_correct).length;
            }, 0);
            
            return {
                model,
                Accuracy: modelData.reduce((sum, item) => sum + item.accuracy, 0) / modelData.length,
                Speed: modelData.reduce((sum, item) => sum + (1/(item.total_time || 1)), 0) / modelData.length,
                Consistency: correctAnswers / totalQuestions,
                'Task Coverage': [...new Set(modelData.map(item => item.tasklist))].length / [...new Set(data.map(item => item.tasklist))].length
            };
        });
    }, [data]);

    const scoreDistribution = useMemo(() => {
        const bins = Array(10).fill(0).map((_, i) => ({
            range: `${i * 10}-${(i + 1) * 10}%`,
            count: 0
        }));
        
        filteredData.forEach(item => {
            const binIndex = Math.floor(item.accuracy * 10);
            if (binIndex >= 0 && binIndex < 10) {
            bins[binIndex].count++;
            }
        });
        
        return bins;
    }, [filteredData]);

    const getTasklistColor = useMemo(() => {
        const tasklists = [...new Set(data.map(item => item.tasklist))];
        
        const colorScale = scaleOrdinal(schemeTableau10)
            .domain(tasklists);
        
        return (tasklist) => colorScale(tasklist);
        }, [data]);

    const totalQuestions = questionStats.length;
    const totalPages = Math.ceil(totalQuestions / questionsPerPage);
    const currentQuestions = questionStats.slice(
    (currentPage - 1) * questionsPerPage,
    currentPage * questionsPerPage
    );

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
            <div className="max-w-full mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-gray-800 mb-2">Evaluation Dashboard</h1>
                    <p className="text-gray-600">Analyze and compare agent performance across different tasks and configurations</p>
                </div>

                {/* File Upload */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                    <div className="flex items-center gap-4">
                        <Upload className="w-5 h-5 text-blue-600" />
                        <label className="flex-1">
                            <span className="text-sm font-medium text-gray-700">Upload JSONL File:</span>
                            <input 
                                type="file"
                                accept=".jsonl,.json"
                                onChange={handleFileUpload}
                                className="block w-full mt-1 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                disabled={loading}
                            />
                        </label>
                        {loading && <span className="text-sm text-blue-600">Loading...</span>}
                        {error && <span className="text-sm text-red-600">{error}</span>}
                        {selectedFile && !loading && <span className="text-sm text-green-600 font-medium">Loaded: {selectedFile}</span>}
                    </div>
                </div>

                {/* Empty state */}
                {data.length === 0 && !loading && (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                        <HelpCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h3 className="text-xl font-medium text-gray-900 mb-2">No Evaluation Data</h3>
                        <p className="text-gray-500 mb-4">
                            Upload a JSONL file containing evaluation results to visualize performance metrics
                        </p>
                        <div className="inline-flex items-center px-4 py-2 bg-blue-50 text-blue-700 rounded-lg">
                            <Upload className="w-4 h-4 mr-2" />
                            <span>Select a JSONL file to begin</span>
                        </div>
                    </div>
                )}

                {data.length > 0 && (
                    <>
                        {/* Filters */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Filter className="w-5 h-5 text-gray-600" />
                                <h3 className="text-lg font-semibold text-gray-800">Filters</h3>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {['model', 'paradigm', 'environment', 'tasklist'].map((field) => (
                                <div key={field}>
                                <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">
                                        {field}
                                </label>
                                <div className="space-y-2 border border-gray-300 rounded-lg p-2">
                                        {/* "All" option */}
                                        <div className="flex items-center">
                                        <input
                                        type="checkbox"
                                        id={`${field}-all`}
                                        checked={(filters[field] || []).includes("all")}
                                        onChange={(e) => {
                                        if (e.target.checked) {
                                                setFilters((prev) => ({
                                                ...prev,
                                                [field]: ["all"],
                                                }));
                                        } else {
                                                setFilters((prev) => ({
                                                ...prev,
                                                [field]: [],
                                                }));
                                        }
                                        }}
                                        className="mr-2"
                                        />
                                        <label htmlFor={`${field}-all`} className="text-sm">
                                        All {field}s
                                        </label>
                                        </div>

                                        {/* Unique values */}
                                        {getUniqueValues(field).map((value) => (
                                        <div key={value} className="flex items-center">
                                        <input
                                        type="checkbox"
                                        id={`${field}-${value}`}
                                        checked={(filters[field] || []).includes(value)}
                                        onChange={(e) => {
                                                const currentValues = filters[field] || [];
                                                if (e.target.checked) {
                                                setFilters((prev) => ({
                                                ...prev,
                                                [field]: [...currentValues.filter((v) => v !== "all"), value],
                                                }));
                                                } else {
                                                setFilters((prev) => ({
                                                ...prev,
                                                [field]: currentValues.filter((v) => v !== value),
                                                }));
                                                }
                                        }}
                                        className="mr-2"
                                        />
                                        <label htmlFor={`${field}-${value}`} className="text-sm">
                                        {value}
                                        </label>
                                        </div>
                                        ))}
                                </div>
                                </div>
                                ))}
                                </div>

                        </div>

                        {/* Summary Stats */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-gray-600">Total Evaluations</p>
                                        <p className="text-2xl font-bold text-gray-900">{filteredData.length}</p>
                                    </div>
                                    <CheckCircle className="w-8 h-8 text-green-500" />
                                </div>
                            </div>
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-gray-600">Avg Accuracy</p>
                                        <p className="text-2xl font-bold text-gray-900">
                                            {filteredData.length > 0 
                                                ? (filteredData.reduce((sum, item) => sum + (item.accuracy || 0), 0) / filteredData.length * 100).toFixed(1)
                                                : 0}%
                                        </p>
                                    </div>
                                    <TrendingUp className="w-8 h-8 text-blue-500" />
                                </div>
                            </div>
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-gray-600">Avg Time</p>
                                        <p className="text-2xl font-bold text-gray-900">
                                            {filteredData.length > 0 
                                                ? (filteredData.reduce((sum, item) => sum + (item.total_time || 0), 0) / filteredData.length).toFixed(1)
                                                : 0}s
                                        </p>
                                    </div>
                                    <Clock className="w-8 h-8 text-orange-500" />
                                </div>
                            </div>
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-gray-600">Unique Models</p>
                                        <p className="text-2xl font-bold text-gray-900">{getUniqueValues('model').length}</p>
                                    </div>
                                    <XCircle className="w-8 h-8 text-purple-500" />
                                </div>
                            </div>
                        </div>

                        {/* Agent Performance Comparison */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <Bot className="w-5 h-5 mr-2 text-indigo-500" />
                                Agent Performance Comparison
                            </h3>
                            <div className="w-full h-[500px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart
                                        data={agentComparison}
                                        margin={{ top: 20, right: 30, left: 20, bottom: 100 }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis 
                                            dataKey="name"
                                            angle={-45}
                                            textAnchor="end"
                                            height={100}
                                            tick={{ fontSize: 12 }}
                                        />
                                        <YAxis 
                                            label={{ 
                                                value: 'Accuracy', 
                                                angle: -90, 
                                                position: 'left' 
                                            }}
                                        />
                                        <Tooltip 
                                            formatter={(value, name) => [
                                                name === 'Accuracy' 
                                                ? `${(value * 100).toFixed(1)}%` 
                                                : `${value.toFixed(1)}s`,
                                                name === 'Accuracy' ? 'Accuracy' : 'Avg Time'
                                            ]}
                                            labelFormatter={value => `Agent: ${value}`}
                                        />
                                        <Bar dataKey="avg_accuracy" fill="#3b82f6" name="Accuracy" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                        
                        {/* Task Difficulty Ranking */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <Flame className="w-5 h-5 mr-2 text-indigo-500" />
                                Task Difficulty Ranking
                            </h3>
                            <div className="w-full h-[500px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart
                                    data={taskDifficulty}
                                    layout="vertical"
                                    margin={{ top: 20, right: 30, left: 150, bottom: 5 }}
                                    >
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis 
                                        type="number"
                                        domain={[0, 1]} 
                                        tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                    />
                                    <YAxis 
                                        dataKey="name" 
                                        type="category" 
                                        tick={{ fontSize: 12 }}
                                        />
                                    <Tooltip 
                                        formatter={(value) => [`${(value * 100).toFixed(1)}%`, 'Difficulty']}
                                        />
                                    <Bar dataKey="difficulty" fill="#ef4444" name="Difficulty">
                                        <LabelList 
                                        dataKey="difficulty" 
                                        position="right" 
                                        formatter={(value) => `${(value * 100).toFixed(1)}%`}
                                        />
                                    </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Accuracy vs Time Scatter Plot */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <Scale className="w-5 h-5 mr-2 text-indigo-500" />
                                Accuracy vs Time Trade-off
                            </h3>
                            <div className="w-full h-[500px]">
                                <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart data={accuracyTimeScatter}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                    type="number"
                                    dataKey="x"
                                    name="Accuracy"
                                    domain={[0, 1]}
                                    tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                    />
                                    <YAxis
                                    type="number"
                                    dataKey="y"
                                    name="Time (s)"
                                    />
                                    <Tooltip
                                    cursor={{ strokeDasharray: '3 3' }}
                                    formatter={(value, name, props) => {
                                        if (name === 'x' || name === 'accuracy') {
                                        return [`${(value * 100).toFixed(1)}%`, 'Accuracy'];
                                        } else if (name === 'y' || name === 'time') {
                                        return [`${value.toFixed(1)}s`, 'Time'];
                                        }
                                        return [value, name];
                                    }}
                                    content={({ active, payload }) => {
                                        if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="bg-white p-3 border border-gray-200 rounded-md shadow-md">
                                            <p className="font-semibold">{data.agent}</p>
                                            <p className="text-sm">Task: {data.tasklist}</p>
                                            <p className="text-sm">Accuracy: <span className="font-medium">{(data.accuracy * 100).toFixed(1)}%</span></p>
                                            <p className="text-sm">Time: <span className="font-medium">{data.time.toFixed(2)}s</span></p>
                                            </div>
                                        );
                                        }
                                        return null;
                                    }}
                                    />
                                    <Scatter 
                                        name="Evaluation Runs"
                                        data={accuracyTimeScatter}
                                        fill="#8884d8"
                                        opacity={0.7}
                                        radius={8}
                                    >
                                        {accuracyTimeScatter.map((entry, index) => (
                                        <Cell 
                                            key={`cell-${index}`} 
                                            fill={getTasklistColor(entry.tasklist)} 
                                        />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="flex flex-wrap gap-2 mt-2">
                                {[...new Set(accuracyTimeScatter.map(item => item.tasklist))].map(tasklist => (
                                    <div key={tasklist} className="flex items-center">
                                    <div 
                                        className="w-3 h-3 rounded-full mr-1" 
                                        style={{ backgroundColor: getTasklistColor(tasklist) }}
                                    />
                                    <span className="text-xs">{tasklist}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Accuracy vs n_steps Scatter Plot */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <Scale className="w-5 h-5 mr-2 text-indigo-500" />
                                Accuracy vs Number of Steps Trade-off
                            </h3>
                            <div className="w-full h-[500px]">
                                <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart data={accuracyStepsScatter}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                    type="number"
                                    dataKey="x"
                                    name="Accuracy"
                                    domain={[0, 1]}
                                    tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                    />
                                    <YAxis
                                    type="number"
                                    dataKey="y"
                                    name="Steps"
                                    />
                                    <Tooltip
                                    cursor={{ strokeDasharray: '3 3' }}
                                    formatter={(value, name, props) => {
                                        if (name === 'x' || name === 'accuracy') {
                                        return [`${(value * 100).toFixed(1)}%`, 'Accuracy'];
                                        } else if (name === 'y' || name === 'n_steps') {
                                        return [`${value.toFixed(1)}`, 'Steps'];
                                        }
                                        return [value, name];
                                    }}
                                    content={({ active, payload }) => {
                                        if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="bg-white p-3 border border-gray-200 rounded-md shadow-md">
                                            <p className="font-semibold">{data.agent}</p>
                                            <p className="text-sm">Task: {data.tasklist}</p>
                                            <p className="text-sm">Accuracy: <span className="font-medium">{(data.accuracy * 100).toFixed(1)}%</span></p>
                                            <p className="text-sm">Steps: <span className="font-medium">{data.n_steps.toFixed(1)}</span></p>
                                            </div>
                                        );
                                        }
                                        return null;
                                    }}
                                    />
                                    <Scatter 
                                        name="Evaluation Runs"
                                        data={accuracyStepsScatter}
                                        fill="#8884d8"
                                        opacity={0.7}
                                        radius={8}
                                    >
                                        {accuracyStepsScatter.map((entry, index) => (
                                        <Cell 
                                            key={`cell-${index}`} 
                                            fill={getTasklistColor(entry.tasklist)} 
                                        />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                                </ResponsiveContainer>
                            </div>
                            <div className="flex flex-wrap gap-2 mt-2">
                                {[...new Set(accuracyStepsScatter.map(item => item.tasklist))].map(tasklist => (
                                    <div key={tasklist} className="flex items-center">
                                    <div 
                                        className="w-3 h-3 rounded-full mr-1" 
                                        style={{ backgroundColor: getTasklistColor(tasklist) }}
                                    />
                                    <span className="text-xs">{tasklist}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Model Task Radar Charts */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <RadarIcon className="w-5 h-5 mr-2 text-indigo-500" />
                                Model Performance by Tasklist
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {modelTaskRadarData.map((modelData, idx) => {
                                    const taskEntries = Object.entries(modelData)
                                        .filter(([key]) => key !== 'model')
                                        .map(([tasklist, accuracy]) => ({
                                            tasklist,
                                            accuracy,
                                            fullAccuracy: (accuracy * 100).toFixed(1) + '%'
                                        }));
                                    
                                    return (
                                        <div key={idx} className="bg-gray-50 rounded-lg p-4">
                                            <h4 className="text-md font-semibold text-gray-700 mb-2 text-center">
                                                {modelData.model}
                                            </h4>
                                            <div className="h-[400px]">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <RadarChart 
                                                        cx="50%" 
                                                        cy="50%" 
                                                        outerRadius="80%" 
                                                        data={taskEntries}
                                                    >
                                                        <PolarGrid />
                                                        <PolarAngleAxis 
                                                            dataKey="tasklist" 
                                                            tick={{ fontSize: 10 }}
                                                        />
                                                        <PolarRadiusAxis 
                                                            angle={30} 
                                                            domain={[0, 1]} 
                                                            tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                                        />
                                                        <Radar 
                                                            name="Accuracy"
                                                            dataKey="accuracy"
                                                            stroke="#3b82f6"
                                                            fill="#3b82f6"
                                                            fillOpacity={0.6}
                                                        >
                                                            <LabelList 
                                                                dataKey="fullAccuracy" 
                                                                position="top" 
                                                            />
                                                        </Radar>
                                                        <Tooltip 
                                                            formatter={(value) => [`${(value * 100).toFixed(1)}%`, 'Accuracy']}
                                                            labelFormatter={(label) => `Task: ${label}`}
                                                        />
                                                    </RadarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Score Distribution Chart */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4">Score Distribution</h3>
                            <div className="w-full h-[300px]">
                                <ResponsiveContainer>
                                <BarChart data={scoreDistribution}>
                                    <XAxis dataKey="range" />
                                    <YAxis />
                                    <Tooltip />
                                    <Bar dataKey="count" fill="#4f46e5" name="Number of Runs" />
                                </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Agent Performance Details */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <BarChart2 className="w-5 h-5 mr-2 text-blue-500" />
                                Agent Performance Details
                            </h3>
                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Paradigm</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Environment</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tasklist</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Accuracy</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time (s)</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {agentPerformanceDetails.map((run, idx) => (
                                            <tr key={idx}>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                    {run.agent}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {run.model}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {run.paradigm}
                                                </td>
                                                <td className="px-6 py-4 whitespace-normal text-sm text-gray-900 max-w-xs">
                                                    <div className="break-all">{run.environment}</div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {run.tasklist}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                                        run.accuracy > 0.8 ? 'bg-green-100 text-green-800' : 
                                                        run.accuracy > 0.6 ? 'bg-yellow-100 text-yellow-800' : 
                                                        'bg-red-100 text-red-800'
                                                    }`}>
                                                        {(run.accuracy * 100).toFixed(1)}%
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {run.total_time.toFixed(2)}s
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Question Difficulty Analysis */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                <List className="w-5 h-5 mr-2 text-purple-500" />
                                Question Difficulty Analysis
                            </h3>
                            
                            {/* Pagination Controls - Top */}
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-sm text-gray-600">
                                Showing {(currentPage - 1) * questionsPerPage + 1} - 
                                {Math.min(currentPage * questionsPerPage, questionStats.length)} of {questionStats.length} questions
                                </div>
                                <div className="flex space-x-2">
                                <button
                                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                    disabled={currentPage === 1}
                                    className={`px-3 py-1 rounded-md ${
                                    currentPage === 1 
                                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                                        : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                                    }`}
                                >
                                    Previous
                                </button>
                                <span className="px-3 py-1 bg-gray-100 rounded-md text-gray-700">
                                    Page {currentPage} of {Math.ceil(questionStats.length / questionsPerPage)}
                                </span>
                                <button
                                    onClick={() => setCurrentPage(p => Math.min(p + 1, Math.ceil(questionStats.length / questionsPerPage)))}
                                    disabled={currentPage >= Math.ceil(questionStats.length / questionsPerPage)}
                                    className={`px-3 py-1 rounded-md ${
                                    currentPage >= Math.ceil(questionStats.length / questionsPerPage) 
                                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                                        : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                                    }`}
                                >
                                    Next
                                </button>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                {/* Table Header */}
                                <thead className="bg-gray-50">
                                    <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Question</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Accuracy</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Time (s)</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Difficulty</th>
                                    </tr>
                                </thead>
                                
                                {/* Table Body */}
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {questionStats
                                    .slice((currentPage - 1) * questionsPerPage, currentPage * questionsPerPage)
                                    .map((stat, idx) => (
                                        <tr key={idx}>
                                        <td className="px-6 py-4 whitespace-normal max-w-prose text-sm text-gray-900">
                                            <div className="whitespace-normal break-words">
                                            {stat.question}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                            stat.accuracy > 0.8 ? 'bg-green-100 text-green-800' : 
                                            stat.accuracy > 0.5 ? 'bg-yellow-100 text-yellow-800' : 
                                            'bg-red-100 text-red-800'
                                            }`}>
                                            {(stat.accuracy * 100).toFixed(1)}%
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            {stat.avgTime.toFixed(2)}s
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <div className="flex items-center">
                                            <div className="w-24 bg-gray-200 rounded-full h-2 mr-2">
                                                <div 
                                                className="bg-red-600 h-2 rounded-full" 
                                                style={{ width: `${stat.difficulty * 100}%` }}
                                                ></div>
                                            </div>
                                            <span>{(stat.difficulty * 100).toFixed(1)}%</span>
                                            </div>
                                        </td>
                                        </tr>
                                    ))
                                    }
                                </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default EvaluationDashboard;