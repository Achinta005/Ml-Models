export async function GET() {
  try {
    // Fetch data from your Python backend
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_EXPRESS_SERVER}/api/projects_data`);

    if (!response.ok) {
      throw new Error(`Python server error: ${response.status}`);
    }

    const data = await response.json();

    return Response.json(data, { status: 200 });
  } catch (error) {
    console.error("Error fetching from Python backend:", error);
    return Response.json({ error: error.message }, { status: 500 });
  }
}
