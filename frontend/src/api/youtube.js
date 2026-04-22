const API_KEY = import.meta.env.VITE_YOUTUBE_API_KEY

const cache = {}

export async function searchYouTubeVideoId(songTitle, artistName) {
  const key = `${songTitle}__${artistName}`
  if (cache[key]) return cache[key]

  const query = `${songTitle} ${artistName} official audio`
  const url = `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${encodeURIComponent(query)}&type=video&maxResults=1&key=${API_KEY}`
  const res = await fetch(url)
  const data = await res.json()
  const videoId = data.items?.[0]?.id?.videoId ?? null
  if (videoId) cache[key] = videoId
  return videoId
}
