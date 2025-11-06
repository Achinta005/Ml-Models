export async function GET() {
    try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_PYTHON_ML_SERVER}/health`);

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