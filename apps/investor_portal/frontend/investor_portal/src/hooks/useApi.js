import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

export const useApi = (endpoint, options) => {
  const { getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;
  const getAuthRef = useRef(getAuthHeaders);
  getAuthRef.current = getAuthHeaders;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: getAuthRef.current(),
        ...(optionsRef.current || {})
      });
      if (!res.ok) throw new Error('Failed to fetch');
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};
